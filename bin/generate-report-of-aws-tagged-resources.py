#!/usr/bin/env python3
import sys, argparse, os
from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta
import boto3
from botocore.config import Config
import botocore
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

# ---------------- CLI ----------------
p = argparse.ArgumentParser(description="Report ParallelCluster-tagged resources and TOTAL historical costs by cluster.")
p.add_argument("--tag-key", default="parallelcluster:cluster-name", help="Cost allocation tag key")
p.add_argument("--since", default="2017-01-01", help="Start date YYYY-MM-DD (default: earliest CE window)")
p.add_argument("--until", default=None, help="End date YYYY-MM-DD EXCLUSIVE (default: tomorrow)")
p.add_argument("--metric", default="AmortizedCost",
               choices=["AmortizedCost","UnblendedCost","NetAmortizedCost","NetUnblendedCost"],
               help="Cost Explorer metric")
p.add_argument("--currency", default=None,
               help="Force currency code (e.g. USD). Uses account currency by default. (Informational)")
p.add_argument("--show-services", type=int, default=4, help="How many top services to list per cluster")
p.add_argument("--budget-name", default="daylily-global", help="Budget name for 'global' line")
p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"), help="AWS profile (env AWS_PROFILE honored)")
p.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2",
               help="Region for Resource Groups Tagging API (defaults to env or us-west-2)")
args = p.parse_args()

# ---------------- Session/clients ----------------
session_kwargs = {}
if args.profile:
    session_kwargs["profile_name"] = args.profile
# Provide a session region so regional clients don't choke.
session_kwargs["region_name"] = args.region
b3 = boto3.Session(**session_kwargs)

# CE + Budgets operate in us-east-1; pin explicitly.
ce = b3.client("ce", region_name="us-east-1",
               config=Config(retries={"max_attempts": 10, "mode": "standard"}))
budgets = b3.client("budgets", region_name="us-east-1",
                    config=Config(retries={"max_attempts": 10, "mode": "standard"}))
# Tagging API is regional; use provided region.
tag = b3.client("resourcegroupstaggingapi", region_name=args.region,
                config=Config(retries={"max_attempts": 10, "mode": "standard"}))

# ---------------- Dates & window caps ----------------
start = date.fromisoformat(args.since)
today = date.today()
end = date.fromisoformat(args.until) if args.until else (today + relativedelta(days=1))  # CE end is exclusive

# Cap CE window to ~14 months of history (older -> ValidationException).
MAX_CE_MONTHS = 14
cap_start = end - relativedelta(months=MAX_CE_MONTHS)
if start < cap_start:
    sys.stderr.write(
        f"[warn] Requested start {start.isoformat()} predates Cost Explorer history. "
        f"Capping to {cap_start.isoformat()} (≈{MAX_CE_MONTHS} months).\n"
    )
    start = cap_start

time_filter = {
    "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
    "Granularity": "MONTHLY",
    "Metrics": [args.metric],
}

# ---------------- Helpers ----------------
def paginate_tag_resources(tag_key: str):
    """
    Iterate all resources that have the given tag key across the chosen region.
    Uses the official paginator; do NOT pass both ResourcesPerPage and TagsPerPage.
    """
    out = []
    paginator = tag.get_paginator("get_resources")
    for page in paginator.paginate(
        TagFilters=[{"Key": tag_key}],
        PaginationConfig={"PageSize": 100},
    ):
        for r in page.get("ResourceTagMappingList", []):
            arn = r["ResourceARN"]
            parts = arn.split(":")
            service = parts[2] if len(parts) > 2 else "unknown"
            region = parts[3] if len(parts) > 3 and parts[3] else "global"
            tags = {t["Key"]: t["Value"] for t in r.get("Tags", [])}
            out.append({"arn": arn, "service": service, "region": region, "tags": tags})
    return out

def ce_total_for_tag(tag_key: str, tag_value: str):
    """
    Sum CE over entire window with pagination; group by SERVICE.
    Includes progressive shrink-retry if CE history is shorter than our capped window.
    """
    # Single-condition filter: don't wrap it in {"And": [...]}
    flt = {"Tags": {"Key": tag_key, "Values": [tag_value], "MatchOptions": ["EQUALS"]}}

    # Make a local copy of time_filter so we can adjust Start safely.
    _time_filter = {
        "TimePeriod": dict(time_filter["TimePeriod"]),
        "Granularity": time_filter["Granularity"],
        "Metrics": list(time_filter["Metrics"]),
    }

    by_service, total, currency = {}, 0.0, None
    token = None
    tries = 0

    while True:
        kwargs = dict(Filter=flt, GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}], **_time_filter)
        if token:
            kwargs["NextPageToken"] = token
        try:
            resp = ce.get_cost_and_usage(**kwargs)
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            msg = e.response.get("Error", {}).get("Message", "")
            # Missing CE perms => friendlier error
            if code in {"AccessDeniedException", "UnauthorizedOperation"}:
                raise SystemExit(
                    "[fatal] CE access denied. Grant ce:GetCostAndUsage and ensure Cost Explorer is enabled in Billing."
                )
            # CE history shorter than our window: tighten and retry up to 3 times (12, 8, 4 months)
            if code == "ValidationException" and "historical data" in msg and tries < 3:
                months = 12 - tries * 4  # 12, 8, 4
                end_iso = _time_filter["TimePeriod"]["End"]
                end_dt = date.fromisoformat(end_iso)
                new_start = end_dt - relativedelta(months=months)
                sys.stderr.write(
                    f"[warn] CE history unavailable for requested window; retrying with start={new_start.isoformat()} (~{months}m).\n"
                )
                _time_filter["TimePeriod"]["Start"] = new_start.isoformat()
                # Reset accumulators and token; try again
                by_service, total, currency = {}, 0.0, None
                token = None
                tries += 1
                continue
            raise

        for rb in resp.get("ResultsByTime", []):
            for grp in rb.get("Groups", []):
                amt = float(grp["Metrics"][args.metric]["Amount"])
                currency = grp["Metrics"][args.metric]["Unit"]
                svc = grp["Keys"][0]
                by_service[svc] = by_service.get(svc, 0.0) + amt
                total += amt

        token = resp.get("NextPageToken")
        if not token:
            break

    return total, by_service, currency

def get_budget_line(budget_name: str):
    sts = b3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    try:
        b = budgets.describe_budget(AccountId=account_id, BudgetName=budget_name)["Budget"]
        limit = float(b["BudgetLimit"]["Amount"])
        unit = b["BudgetLimit"]["Unit"]
        actual = float(b.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount", "0"))
        forecast = float(b.get("CalculatedSpend", {}).get("ForecastedSpend", {}).get("Amount", "0"))
        return {"limit": limit, "actual": actual, "forecast": forecast, "unit": unit}
    except budgets.exceptions.NotFoundException:
        return None

# ---------------- Inventory ----------------
try:
    resources = paginate_tag_resources(args.tag_key)
except Exception as e:
    raise SystemExit(f"[fatal] Failed to list tagged resources in region {args.region}: {e}")

by_cluster = defaultdict(list)
for r in resources:
    val = r["tags"].get(args.tag_key)
    if val:
        by_cluster[val].append(r)

# ---------------- Render ----------------
console = Console()
table = Table(box=box.SIMPLE_HEAVY)
table.add_column("Cluster (tag value)", style="bold")
table.add_column("Resources", justify="right")
table.add_column("Services (top N)", overflow="fold")
table.add_column(f"TOTAL {args.metric}", justify="right")

grand_total = 0.0
currency_seen = None

for cluster in sorted(by_cluster.keys()):
    total_cost, svc_map, currency = ce_total_for_tag(args.tag_key, cluster)
    currency_seen = currency or currency_seen
    svc_sorted = sorted(svc_map.items(), key=lambda kv: kv[1], reverse=True)
    topk = svc_sorted[:args.show_services]
    others = sum(v for _, v in svc_sorted[args.show_services:])
    svc_frag = ", ".join(f"{k}:{v:.2f}" for k, v in topk) if topk else "—"
    if others > 0:
        svc_frag += f", others:{others:.2f}"

    cost_txt = Text(f"{total_cost:.2f} {currency or ''}")
    if total_cost >= 10000:
        cost_txt.stylize("red bold")
    elif total_cost >= 2000:
        cost_txt.stylize("yellow")
    else:
        cost_txt.stylize("green")

    res_count = len(by_cluster[cluster])
    table.add_row(cluster, str(res_count), svc_frag, cost_txt)
    grand_total += total_cost

# -------- Global budget status line
budget = get_budget_line(args.budget_name)
if budget:
    util = (budget["actual"] / budget["limit"] * 100.0) if budget["limit"] > 0 else 0.0
    util_txt = Text(f"{budget['actual']:.2f}/{budget['limit']:.2f} {budget['unit']} ({util:.1f}%)")
    if util >= 90:
        util_txt.stylize("red bold")
    elif util >= 70:
        util_txt.stylize("yellow")
    else:
        util_txt.stylize("green")
    table.add_row("global", "—", f"budget:{args.budget_name}", util_txt)
else:
    table.add_row("global", "—", f"budget:{args.budget-name}", Text("not found", style="dim"))

console.print(table)
gtxt = Text(f"Grand total (clusters) TOTAL {args.metric}: {grand_total:.2f} {currency_seen or ''}")
gtxt.stylize("bold")
console.print(gtxt)
console.print(
    Text(
        f"Window: {start.isoformat()} → {end.isoformat()} (CE end exclusive) | tag-region: {args.region} | CE/Budgets: us-east-1",
        style="dim",
    )
)
