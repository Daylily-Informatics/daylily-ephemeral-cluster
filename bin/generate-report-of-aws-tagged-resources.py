#!/usr/bin/env python3
import sys
import argparse
import os
from collections import defaultdict, Counter
from datetime import date

# Ensure DAY-EC conda environment is active
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers"))
from ensure_dayec import ensure_dayec
ensure_dayec(quiet=True)

from dateutil.relativedelta import relativedelta
import boto3
import botocore
from botocore.config import Config
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

# ---------- CLI ----------
p = argparse.ArgumentParser(description="Report ParallelCluster-tagged resources and TOTAL historical costs by cluster.")
p.add_argument("--tag-key", default="parallelcluster:cluster-name", help="Cost allocation tag key")
p.add_argument("--since", default="2017-01-01", help="Start date YYYY-MM-DD")
p.add_argument("--until", default=None, help="End date YYYY-MM-DD EXCLUSIVE (default: tomorrow)")
p.add_argument("--metric", default="AmortizedCost",
               choices=["AmortizedCost","UnblendedCost","NetAmortizedCost","NetUnblendedCost"])
p.add_argument("--top-n", type=int, default=4, help="Top-N services to display in each column")
p.add_argument("--budget-name", default="daylily-global", help="Budget name for 'global' line")
p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"), help="AWS profile (env AWS_PROFILE honored)")
p.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2",
               help="Region for Resource Groups Tagging API (defaults to env or us-west-2)")

# New filters
p.add_argument("--show-services", default="all",
               help="CSV of service keys to include (e.g. 'logs,sns,ec2,fsx'). 'all' (default) = no include filter.")
p.add_argument("--exclude-services", default="",
               help="CSV of service keys to exclude (e.g. 'logs,sns,fsx,ec2').")
p.add_argument("--only-show-active", action="store_true",
               help="If set, only show clusters whose discovered services include more than just 'logs'/CloudWatch.")
args = p.parse_args()

# ---------- Session / clients ----------
session_kwargs = {"region_name": args.region}
if args.profile:
    session_kwargs["profile_name"] = args.profile
b3 = boto3.Session(**session_kwargs)
ce = b3.client("ce", region_name="us-east-1", config=Config(retries={"max_attempts": 10, "mode": "standard"}))
budgets = b3.client("budgets", region_name="us-east-1", config=Config(retries={"max_attempts": 10, "mode": "standard"}))
tag = b3.client("resourcegroupstaggingapi", region_name=args.region, config=Config(retries={"max_attempts": 10, "mode": "standard"}))

# ---------- Dates ----------
user_start = date.fromisoformat(args.since)
today = date.today()
end = date.fromisoformat(args.until) if args.until else (today + relativedelta(days=1))  # CE end is exclusive

cap_start = end - relativedelta(months=14)
if user_start < cap_start:
    sys.stderr.write(f"[warn] Requested start {user_start.isoformat()} predates CE history; capping to {cap_start.isoformat()}.\n")
    user_start = cap_start

def find_earliest_ce_start(ce_client, end_dt: date, metric: str) -> date:
    for months in (12, 9, 6, 3, 2, 1):
        test_start = end_dt - relativedelta(months=months)
        try:
            ce_client.get_cost_and_usage(
                TimePeriod={"Start": test_start.isoformat(), "End": end_dt.isoformat()},
                Granularity="MONTHLY",
                Metrics=[metric],
            )
            return test_start
        except botocore.exceptions.ClientError as e:
            msg = e.response.get("Error", {}).get("Message", "")
            if "historical data" not in msg:
                raise
    sys.stderr.write("[warn] CE appears newly enabled; falling back to 30 days.\n")
    return end_dt - relativedelta(days=30)

earliest = find_earliest_ce_start(ce, end, args.metric)
if user_start < earliest:
    sys.stderr.write(f"[warn] Tightening CE start to {earliest.isoformat()} based on availability.\n")
    user_start = earliest

time_filter = {"TimePeriod": {"Start": user_start.isoformat(), "End": end.isoformat()},
               "Granularity": "MONTHLY", "Metrics": [args.metric]}

# ---------- Service normalization & filters ----------
def _tokset(csv_str: str):
    if not csv_str or csv_str.strip().lower() == "all":
        return None
    return {t.strip().lower() for t in csv_str.split(",") if t.strip()}

# Canonicalize service names so user tokens like 'ec2,fsx,logs,sns' match both ARN tokens and CE marketing names.
def canonical_service(name: str, source: str) -> str:
    n = (name or "").strip().lower()
    if source == "arn":
        # ARN service tokens are already compact (ec2, s3, logs, fsx, route53, apigateway, secretsmanager, ecr, elasticfilesystem, elasticloadbalancing, autoscaling, etc.)
        return n
    # CE SERVICE dimension values → map to compact tokens
    # Key patterns:
    if "elastic compute cloud" in n: return "ec2"
    if "fsx" in n: return "fsx"
    if "simple notification service" in n: return "sns"
    if "simple storage service" in n or n == "amazon s3": return "s3"
    if "cloudwatch" in n: return "cloudwatch"  # treat 'logs' ~ 'cloudwatch'
    if "elastic file system" in n: return "elasticfilesystem"
    if "elastic load balancing" in n: return "elasticloadbalancing"
    if n.startswith("amazon ecr") or "elastic container registry" in n: return "ecr"
    if "route 53" in n: return "route53"
    if "api gateway" in n: return "apigateway"
    if "secrets manager" in n: return "secretsmanager"
    # Fall back: last token-ish
    return n.replace("amazon ", "").replace("aws ", "").strip()

include_set = _tokset(args.show_services)  # None means include all
exclude_set = _tokset(args.exclude_services) or set()

def allowed_service(token: str) -> bool:
    t = token
    # Treat user 'logs' as 'cloudwatch' equivalent
    if t == "logs":
        t = "cloudwatch"
    if include_set is not None and t not in include_set:
        return False
    if t in exclude_set:
        return False
    return True

# ---------- Helpers ----------
def paginate_tag_resources(tag_key):
    out = []
    paginator = tag.get_paginator("get_resources")
    for page in paginator.paginate(TagFilters=[{"Key": tag_key}], PaginationConfig={"PageSize": 100}):
        for r in page.get("ResourceTagMappingList", []):
            arn = r["ResourceARN"]
            parts = arn.split(":")
            svc = parts[2] if len(parts) > 2 else "unknown"
            tags = {t["Key"]: t["Value"] for t in r.get("Tags", [])}
            out.append({"service": svc.lower(), "tags": tags})
    return out

def ce_total_for_tag(tag_key, tag_val):
    flt = {"Tags": {"Key": tag_key, "Values": [tag_val], "MatchOptions": ["EQUALS"]}}
    total, by_service, currency = 0.0, {}, None
    token = None
    while True:
        kw = dict(Filter=flt, GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}], **time_filter)
        if token: kw["NextPageToken"] = token
        resp = ce.get_cost_and_usage(**kw)
        for rb in resp.get("ResultsByTime", []):
            for grp in rb.get("Groups", []):
                svc_dim = grp["Keys"][0]
                amt = float(grp["Metrics"][args.metric]["Amount"])
                currency = grp["Metrics"][args.metric]["Unit"]
                canon = canonical_service(svc_dim, source="ce")
                if allowed_service(canon):
                    by_service[svc_dim] = by_service.get(svc_dim, 0.0) + amt  # keep pretty CE name for display
                    total += amt
        token = resp.get("NextPageToken")
        if not token: break
    return total, by_service, currency

def get_budget_line(name):
    aid = b3.client("sts").get_caller_identity()["Account"]
    try:
        b = budgets.describe_budget(AccountId=aid, BudgetName=name)["Budget"]
        lim = float(b["BudgetLimit"]["Amount"]); unit = b["BudgetLimit"]["Unit"]
        act = float(b.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount", "0"))
        fcast = float(b.get("CalculatedSpend", {}).get("ForecastedSpend", {}).get("Amount", "0"))
        return {"limit": lim, "actual": act, "forecast": fcast, "unit": unit}
    except budgets.exceptions.NotFoundException:
        return None

# ---------- Inventory ----------
try:
    resources = paginate_tag_resources(args.tag_key)
except Exception as e:
    raise SystemExit(f"[fatal] Tagging API error in region {args.region}: {e}")

by_cluster = defaultdict(list)
for r in resources:
    val = r["tags"].get(args.tag_key)
    if val:
        by_cluster[val].append(r)

# ---------- Render ----------
console = Console()
table = Table(box=box.SIMPLE_HEAVY)
table.add_column("Cluster (tag value)", style="bold")
table.add_column("Resources", justify="right")
table.add_column("Discovered Services (top N)", overflow="fold")  # inventory presence
table.add_column("Active Services (top N)", overflow="fold")      # spend
table.add_column(f"TOTAL {args.metric}", justify="right")

grand_total = 0.0
currency_seen = None

for cluster in sorted(by_cluster.keys()):
    # Inventory services (from ARNs)
    inv_tokens = [canonical_service(s["service"], source="arn") for s in by_cluster[cluster]]
    # Normalize logs->cloudwatch for filtering, but display original token names (short)
    inv_counts = Counter([("cloudwatch" if t == "logs" else t) for t in inv_tokens])
    # Apply include/exclude
    inv_counts = Counter({k: v for k, v in inv_counts.items() if allowed_service(k)})

    non_cw_services = {k for k in inv_counts.keys() if k != "cloudwatch"}
    is_active = bool(non_cw_services)
    # --only-show-active: skip clusters with only 'cloudwatch' services (or empty after filters)
    if args.only_show_active and not is_active:
        continue

    # Active services/spend (CE)
    total_cost, ce_svc_map, currency = ce_total_for_tag(args.tag_key, cluster)
    currency_seen = currency or currency_seen

    # Build strings
    top_disc = inv_counts.most_common(args.top_n)
    disc_str = ", ".join(f"{k}:{v}" for k, v in top_disc) if top_disc else "—"

    svc_sorted = sorted(ce_svc_map.items(), key=lambda kv: kv[1], reverse=True)
    topk = svc_sorted[:args.top_n]
    others = sum(v for _, v in svc_sorted[args.top_n:])
    act_str = ", ".join(f"{k}:{v:.2f}" for k, v in topk) if topk else "—"
    if others > 0:
        act_str += f", others:{others:.2f}"

    cost_styles = []
    if total_cost >= 10000: cost_styles.append("red bold")
    elif total_cost >= 2000: cost_styles.append("yellow")
    else: cost_styles.append("green")

    if not is_active:
        cost_styles.append("on darkgray")

    cost_txt = Text(f"{total_cost:.2f} {currency or ''}", style=" ".join(cost_styles))

    table.add_row(cluster, str(len(by_cluster[cluster])), disc_str, act_str, cost_txt)
    grand_total += total_cost

# ---------- Global budget ----------
budget = get_budget_line(args.budget_name)
if budget:
    util = (budget["actual"] / budget["limit"] * 100.0) if budget["limit"] > 0 else 0.0
    util_txt = Text(f"{budget['actual']:.2f}/{budget['limit']:.2f} {budget['unit']} ({util:.1f}%)")
    if util >= 90: util_txt.stylize("red bold")
    elif util >= 70: util_txt.stylize("yellow")
    else: util_txt.stylize("green")
    table.add_row("global", "—", f"budget:{args.budget_name}", "—", util_txt)
else:
    table.add_row("global", "—", f"budget:{args.budget_name}", "—", Text("not found", style="dim"))

console.print(table)
gtxt = Text(f"Grand total (clusters) TOTAL {args.metric}: {grand_total:.2f} {currency_seen or ''}", style="bold")
console.print(gtxt)
console.print(Text(f"Window: {user_start.isoformat()} → {end.isoformat()} (CE end exclusive) | tag-region: {args.region} | CE/Budgets: us-east-1", style="dim"))

gtxt = Text(f"WARNING: resources can lag by up to a day before appearing -OR- dissappearing from this report!" ,style="bold")
console.print(gtxt)