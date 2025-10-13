#!/usr/bin/env python3
import sys, argparse, itertools, os
from collections import defaultdict, Counter
from datetime import date
from dateutil.relativedelta import relativedelta
import boto3
from botocore.config import Config
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

p = argparse.ArgumentParser(description="Report ParallelCluster-tagged resources and TOTAL historical costs by cluster.")
p.add_argument("--tag-key", default="parallelcluster:cluster-name", help="Cost allocation tag key")
p.add_argument("--since", default="2017-01-01", help="Start date YYYY-MM-DD (default: earliest CE window)")
p.add_argument("--until", default=None, help="End date YYYY-MM-DD EXCLUSIVE (default: tomorrow)")
p.add_argument("--metric", default="AmortizedCost", choices=["AmortizedCost","UnblendedCost","NetAmortizedCost","NetUnblendedCost"], help="Cost Explorer metric")
p.add_argument("--currency", default=None, help="Force currency code (e.g. USD). Uses account currency by default.")
p.add_argument("--show-services", type=int, default=4, help="How many top services to list per cluster")
p.add_argument("--budget-name", default="daylily-global", help="Budget name for 'global' line")
p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"), help="AWS profile (env AWS_PROFILE honored)")
args = p.parse_args()

session_kwargs = {}
if args.profile: session_kwargs["profile_name"] = args.profile
b3 = boto3.Session(**session_kwargs)
ce = b3.client("ce", config=Config(retries={"max_attempts": 10, "mode": "standard"}))
budgets = b3.client("budgets", region_name="us-east-1")
tag = b3.client("resourcegroupstaggingapi", config=Config(retries={"max_attempts": 10, "mode": "standard"}))

# -------- Dates
start = date.fromisoformat(args.since)
today = date.today()
end = date.fromisoformat(args.until) if args.until else (today + relativedelta(days=1))  # CE end is exclusive
time_filter = {"TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
               "Granularity": "MONTHLY",
               "Metrics": [args.metric]}

# -------- Helpers
def paginate_tag_resources(tag_key):
    out, token = [], None
    while True:
        kwargs = {"TagFilters": [{"Key": tag_key}], "ResourcesPerPage": 100, "TagsPerPage": 100}
        if token: kwargs["PaginationToken"] = token
        resp = tag.get_resources(**kwargs)
        for r in resp.get("ResourceTagMappingList", []):
            arn = r["ResourceARN"]
            parts = arn.split(":")
            service = parts[2] if len(parts) > 2 else "unknown"
            region = parts[3] if len(parts) > 3 and parts[3] else "global"
            tags = {t["Key"]: t["Value"] for t in r.get("Tags", [])}
            out.append({"arn": arn, "service": service, "region": region, "tags": tags})
        token = resp.get("PaginationToken")
        if not token: break
    return out

def ce_total_for_tag(tag_key, tag_value):
    flt = {"And": [{"Tags": {"Key": tag_key, "Values": [tag_value], "MatchOptions": ["EQUALS"]}}]}
    # Group by SERVICE to provide a quick per-cluster top-N breakdown; then sum across months.
    resp = ce.get_cost_and_usage(Filter=flt, **time_filter, GroupBy=[{"Type": "DIMENSION","Key":"SERVICE"}])
    currency = None
    by_service = {}
    total = 0.0
    for rb in resp["ResultsByTime"]:
        for grp in rb["Groups"]:
            amt = float(grp["Metrics"][args.metric]["Amount"])
            currency = grp["Metrics"][args.metric]["Unit"]
            svc = grp["Keys"][0]
            by_service[svc] = by_service.get(svc, 0.0) + amt
            total += amt
    # Note: CE will return zeroes for months before tag activation.
    return total, by_service, currency

def get_budget_line(budget_name):
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

# -------- Inventory
resources = paginate_tag_resources(args.tag_key)
by_cluster = defaultdict(list)
for r in resources:
    val = r["tags"].get(args.tag_key)
    if val: by_cluster[val].append(r)

# -------- Render
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
    if others > 0: svc_frag += f", others:{others:.2f}"

    cost_txt = Text(f"{total_cost:.2f} {currency or ''}")
    if total_cost >= 10000: cost_txt.stylize("red bold")
    elif total_cost >= 2000: cost_txt.stylize("yellow")
    else: cost_txt.stylize("green")

    svc_counts = Counter([r["service"] for r in by_cluster[cluster]])
    res_count = len(by_cluster[cluster])
    svc_brief = ", ".join(f"{k}:{v}" for k, v in svc_counts.most_common(4))
    table.add_row(cluster, str(res_count), svc_brief if svc_brief else "—", cost_txt)
    grand_total += total_cost

# -------- Global budget status line
budget = get_budget_line(args.budget_name)
if budget:
    util = (budget["actual"] / budget["limit"] * 100.0) if budget["limit"] > 0 else 0.0
    util_txt = Text(f"{budget['actual']:.2f}/{budget['limit']:.2f} {budget['unit']} ({util:.1f}%)")
    if util >= 90: util_txt.stylize("red bold")
    elif util >= 70: util_txt.stylize("yellow")
    else: util_txt.stylize("green")
    table.add_row("global", "—", f"budget:{args.budget_name}", util_txt)
else:
    table.add_row("global", "—", f"budget:{args.budget_name}", Text("not found", style="dim"))

console.print(table)
gtxt = Text(f"Grand total (clusters) TOTAL {args.metric}: {grand_total:.2f} {currency_seen or ''}")
gtxt.stylize("bold")
console.print(gtxt)
console.print(Text(f"Window: {start.isoformat()} → {end.isoformat()} (CE end exclusive)", style="dim"))
