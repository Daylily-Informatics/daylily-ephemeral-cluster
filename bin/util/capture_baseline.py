#!/usr/bin/env python3
"""Capture the API calls a real Daylily deploy made, bucketed by principal.

Reads CloudTrail Event History (always-on, 90 days, management events) for a time
window and splits what happened into the buckets that map to different IAM roles:

  deployer            calls made directly by the deploying principal
  deployer-via-cfn    calls CloudFormation made USING the deployer's credentials
                      -> these still need to be in the DEPLOYER policy
  instance-role       calls from cluster node roles at runtime
                      -> these belong to the NODE roles, not the deployer
  service             AWS services acting on their own service-linked roles
                      -> needs no permission from anyone

Conflating instance-role calls into the deployer policy is the main way this
exercise produces a far-too-broad role, so the split is the point.

Usage
-----
  python capture_baseline.py --start 2026-08-13T14:00:00Z --end 2026-08-13T16:00:00Z \
      --region us-west-2 --profile lsmc-dev --principal DaylilyBaselineDeploy

  # compare the observed deployer actions against the ISS-73 derived set
  python capture_baseline.py ... --compare-derived

Notes
-----
* S3 object-level calls will NOT appear — management events only. The S3 scope
  comes from the ISS-63 decision, not from this capture.
* lookup-events is rate limited (~2 req/s); this paginates politely.
* Run once per region the deploy touched.
* **Global services log to us-east-1, not to the deploy region.** IAM, STS,
  budgets and Route 53 events are recorded in the global trail regardless of
  where you deployed, so a single-region scan reports *zero IAM activity* and
  invites the conclusion that the deployer needs no IAM permissions. It does:
  a 2026-08-14 us-west-2 baseline made 95 IAM write calls (12 CreateRole,
  10 CreateInstanceProfile, 30 AttachRolePolicy, 33 PutRolePolicy,
  10 AddRoleToInstanceProfile), every one of them invisible in us-west-2.
  This script therefore scans --region AND --global-region and merges.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time

import boto3

# Services whose CloudTrail events are recorded in the global (us-east-1) trail
# rather than the region the request was made from. When scanning the global
# region we keep ONLY these, so unrelated us-east-1 regional activity does not
# get mistaken for part of the deploy.
GLOBAL_EVENT_SOURCES = frozenset({
    "iam", "sts", "route53", "route53domains", "cloudfront", "budgets",
    "ce", "pricing", "organizations", "support", "health", "waf", "shield",
    "globalaccelerator", "networkmanager",
})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", required=True, help="ISO8601 UTC, e.g. 2026-08-13T14:00:00Z")
    p.add_argument("--end", required=True, help="ISO8601 UTC")
    p.add_argument("--region", default="us-west-2")
    p.add_argument("--global-region", default="us-east-1",
                   help="Region holding the global trail (IAM/STS/budgets/Route 53). "
                        "Scanned in addition to --region; pass '' to skip, which "
                        "will hide every IAM call the deploy made.")
    p.add_argument("--profile", default=None)
    p.add_argument("--principal", default="",
                   help="Substring of the deploying role/user ARN, e.g. DaylilyBaselineDeploy. "
                        "Everything else is bucketed separately.")
    p.add_argument("--out", default="baseline_capture.json")
    p.add_argument("--compare-derived", action="store_true",
                   help="Diff observed deployer actions against DYEC's _permission_groups()")
    return p.parse_args()


def iso(value: str):
    from datetime import datetime
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classify(detail: dict, principal_hint: str) -> str:
    ident = detail.get("userIdentity", {}) or {}
    itype = ident.get("type", "")
    arn = ident.get("arn", "") or ""
    issuer = (ident.get("sessionContext", {}) or {}).get("sessionIssuer", {}) or {}
    issuer_arn = issuer.get("arn", "") or ""
    invoked_by = detail.get("invokedBy", "") or ""

    is_deployer = bool(principal_hint) and (
        principal_hint in arn or principal_hint in issuer_arn
    )

    if itype == "AWSService":
        return "service"
    if is_deployer and invoked_by.endswith("amazonaws.com"):
        # CloudFormation (etc.) acting with the deployer's credentials — the
        # deployer policy must still permit these.
        return "deployer-via-cfn"
    if is_deployer:
        return "deployer"
    if "/parallelcluster/" in issuer_arn or "RoleHeadNode" in issuer_arn or "ComputeFleet" in issuer_arn:
        return "instance-role"
    if invoked_by.endswith("amazonaws.com"):
        return "service"
    return "other"


def plan_scans(region: str, global_region: str) -> list[tuple[str, bool]]:
    """Return [(region, global_sources_only), ...] to cover regional AND global events.

    Global services (IAM, STS, budgets, Route 53) record into one region's trail
    no matter where the request originated, so a single-region scan silently
    omits every IAM call a deploy makes. When the deploy region already IS the
    global region, one unfiltered pass covers both.
    """
    global_region = (global_region or "").strip()
    scans = [(region, False)]
    if global_region and global_region != region:
        scans.append((global_region, True))
    return scans


def scan_region(session, region, args, buckets, errors, principals, by_region,
                *, global_sources_only: bool) -> int:
    """Page one region's Event History into the shared counters. Returns pages read."""
    ct = session.client("cloudtrail", region_name=region)
    scope = "global-service events only" if global_sources_only else "all events"
    print(f"reading CloudTrail {region} ({scope})  {args.start} -> {args.end}",
          file=sys.stderr)

    pages = 0
    token = None
    while True:
        kwargs = {"StartTime": iso(args.start), "EndTime": iso(args.end), "MaxResults": 50}
        if token:
            kwargs["NextToken"] = token
        try:
            resp = ct.lookup_events(**kwargs)
        except Exception as exc:            # throttling or permission
            print(f"lookup_events failed in {region}: {exc}", file=sys.stderr)
            raise

        for event in resp.get("Events", []):
            try:
                detail = json.loads(event.get("CloudTrailEvent", "{}"))
            except json.JSONDecodeError:
                continue
            source = (detail.get("eventSource") or "").split(".")[0]
            name = detail.get("eventName") or ""
            if not source or not name:
                continue
            # The global trail also carries that region's own regional activity;
            # keeping it would conflate another region's work with this deploy.
            if global_sources_only and source not in GLOBAL_EVENT_SOURCES:
                continue
            action = f"{source}:{name}"
            bucket = classify(detail, args.principal)
            buckets[bucket][action] += 1
            by_region[region][action] += 1
            ident = detail.get("userIdentity", {}) or {}
            principals[ident.get("arn") or ident.get("type") or "?"] += 1
            if detail.get("errorCode"):
                errors[f"{action} [{detail['errorCode']}]"] += 1

        pages += 1
        token = resp.get("NextToken")
        if not token:
            break
        time.sleep(0.6)                      # stay under the ~2 req/s limit
        if pages % 20 == 0:
            print(f"  [{region}] ...{pages} pages", file=sys.stderr)
    return pages


def main() -> int:
    args = parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)

    buckets: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    errors: collections.Counter = collections.Counter()
    principals: collections.Counter = collections.Counter()
    by_region: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    # Deploy region first, then the global trail. When the deploy region IS the
    # global region one unfiltered pass already covers both.
    global_region = (args.global_region or "").strip()
    scans = plan_scans(args.region, global_region)
    if len(scans) == 1 and global_region != args.region:
        print("NOTE: --global-region is empty, so IAM/STS/budgets/Route 53 calls "
              "will be missing from this capture.", file=sys.stderr)

    pages = 0
    try:
        for region, globals_only in scans:
            pages += scan_region(session, region, args, buckets, errors, principals,
                                 by_region, global_sources_only=globals_only)
    except Exception:
        return 1

    # ---- report ----------------------------------------------------------
    print(f"\npages read: {pages}")
    for region, actions in by_region.items():
        print(f"  {region}: {len(actions)} distinct actions, {sum(actions.values())} events")
    print()
    print("principals seen:")
    for arn, n in principals.most_common(12):
        print(f"  {n:6}  {arn}")

    print("\nactions by bucket:")
    for bucket in ("deployer", "deployer-via-cfn", "instance-role", "service", "other"):
        actions = buckets.get(bucket)
        if not actions:
            continue
        print(f"\n  [{bucket}] {len(actions)} distinct actions")
        for action, n in sorted(actions.items()):
            print(f"     {n:5}  {action}")

    deployer_actions = sorted(set(buckets["deployer"]) | set(buckets["deployer-via-cfn"]))
    print(f"\n==> DEPLOYER POLICY CANDIDATE: {len(deployer_actions)} actions")
    print("    (deployer + deployer-via-cfn; instance-role deliberately excluded)")

    # IAM writes are the whole point of the project, so surface them explicitly
    # rather than leaving them buried in a 100-line action list.
    iam_writes = {
        a: n for a, n in buckets["deployer"].items()
        if a.startswith("iam:") and not a.split(":")[1].startswith(("Get", "List", "Simulate"))
    }
    iam_writes.update({
        a: n for a, n in buckets["deployer-via-cfn"].items()
        if a.startswith("iam:") and not a.split(":")[1].startswith(("Get", "List", "Simulate"))
    })
    print(f"\n==> IAM WRITES BY THE DEPLOYER: {sum(iam_writes.values())} calls, "
          f"{len(iam_writes)} distinct actions")
    if iam_writes:
        for action, n in sorted(iam_writes.items()):
            print(f"     {n:5}  {action}")
        print("    Each of these disappears if ParallelCluster is handed pre-created")
        print("    InstanceProfiles instead of creating roles itself (deliverable B4).")
    else:
        print("     none — if you expected some, check that the global trail was scanned")

    if errors:
        print("\nfailed calls in window (investigate before trusting the set):")
        for k, n in errors.most_common(25):
            print(f"  {n:5}  {k}")

    payload = {
        "window": {
            "start": args.start,
            "end": args.end,
            "region": args.region,
            "global_region": global_region or None,
            "regions_scanned": [r for r, _ in scans],
        },
        "principal_hint": args.principal,
        "buckets": {k: dict(v) for k, v in buckets.items()},
        "by_region": {k: dict(v) for k, v in by_region.items()},
        "deployer_policy_candidate": deployer_actions,
        "deployer_iam_writes": dict(sorted(iam_writes.items())),
        "errors": dict(errors),
        "caveat": "management events only — S3 object-level calls are absent by design",
    }
    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    print(f"\nwrote {args.out}")

    # ---- optional cross-check against the ISS-73 derived set --------------
    if args.compare_derived:
        try:
            from daylily_ec.aws.validation import _permission_groups
        except ImportError:
            print("\n(--compare-derived needs the DAY-EC env; skipped)", file=sys.stderr)
            return 0

        # DYEC 18.0.17's _permission_groups() reads aws_ctx.caller_arn to derive
        # the partition (validation.py:2145); the 7.x shim supplied only
        # account_id/region and now raises AttributeError. Take the real identity
        # rather than fabricating one, so the partition and account are correct.
        try:
            ident = session.client("sts").get_caller_identity()
            _account, _arn = ident["Account"], ident["Arn"]
        except Exception as exc:
            print(f"\n(--compare-derived needs sts:GetCallerIdentity: {exc}; skipped)",
                  file=sys.stderr)
            return 0

        class Ctx:
            account_id = _account
            caller_arn = _arn
            region = args.region

        try:
            derived = {a for g in _permission_groups(Ctx()) for a in g.actions}
        except Exception as exc:
            print(f"\n(--compare-derived: _permission_groups() signature changed "
                  f"in this DYEC version: {exc}; skipped)", file=sys.stderr)
            return 0
        observed = set(deployer_actions)

        missing = sorted(
            o for o in observed
            if o not in derived and not any(
                d.endswith("*") and o.startswith(d[:-1]) for d in derived)
        )
        unused = sorted(
            d for d in derived
            if d not in observed and not d.endswith("*")
        )
        print(f"\n=== CROSS-CHECK vs ISS-73 derived set ({len(derived)} actions) ===")
        print(f"\nOBSERVED but NOT derived — real gaps we would have shipped ({len(missing)}):")
        for a in missing:
            print(f"  + {a}")
        print(f"\nDERIVED but never observed — candidates to drop ({len(unused)}):")
        for a in unused:
            print(f"  - {a}")
        print("\nNote: 'never observed' only means 'not in this window'. A path the "
              "baseline did not exercise (image build, cluster update, teardown) will "
              "look unused. Confirm coverage before dropping anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
