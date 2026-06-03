# Headnode Ultima Analysis Cleanup Ledger

Created: 2026-05-18T02:39Z

## Objective

Prepare deletion of Ultima data-analysis directories from the headnode FSx analysis-results area:

```text
/fsx/analysis_results/ubuntu
```

No live filesystem deletion is authorized until the operator gives a second explicit confirmation after reviewing the exact destructive effect.

## Gate 0: Inventory Freeze

Status: `SUCCESS`

Local repo:

```text
/Users/jmajor/projects/daylily/daylily-ephemeral-cluster
## codex/run-directory-mounts...origin/codex/run-directory-mounts
```

Remote cluster:

```text
cluster=may26-d
region=us-west-2
profile=lsmc
headnode=i-0e7639ff46f207ae7
remote_user=ubuntu
```

Remote filesystem at inventory time:

```text
Filesystem                Size  Used Avail Use% Mounted on
10.0.1.105@tcp:/ynjjzb4v   11T  7.9T  3.1T  73% /fsx
```

Inventory command:

```text
DayEC SSM run_shell as ubuntu, command_id=65ebfa47-4c1c-41e6-9b60-567c72f004da
```

Candidate detection rule:

- Include directories under `/fsx/analysis_results/ubuntu` whose name indicates Ultima work or whose DayOA `config/units.tsv` evidence shows `SEQ_PLATFORM=ULTIMA` / Ultima run IDs.
- Exclude name matches that are not Ultima by config evidence.

## Delete Candidates

| Directory | Bytes | Human | Evidence |
|---|---:|---:|---|
| `/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z` | 74,071,089,692 | 70G | `config/units.tsv`: `platform=ULTIMA`, `runids=602202-20260512-1805`. |
| `/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z` | 75,281,542,398 | 71G | `config/units.tsv`: `platform=ULTIMA`, `runids=602202-20260512-1805`. |

Total delete candidate size:

```text
149,352,632,090 bytes
about 141G
```

## Excluded Name Match

| Directory | Bytes | Human | Reason Excluded |
|---|---:|---:|---|
| `/fsx/analysis_results/ubuntu/v100_ksink` | 29,931,701,436 | 29G | Name matched `v100`, but `config/units.tsv` shows `platform=NOVASEQ`, `runids=v100-ksink-20260517T152929Z`; not Ultima. |

## Active Reference Check

At inventory time:

- Slurm had no jobs with Ultima/602202 work names.
- Tmux still had session `ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z`.
- `pgrep` showed two `tee` processes writing `/home/ubuntu/daylily-runs/ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z/ksink101_downstream.log`; those are not in `/fsx/analysis_results/ubuntu`, but they indicate the old tmux/controller surface was still present.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| HUC-001 | Safety | Inventory exact headnode FSx directories before deletion. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | SSM command `65ebfa47-4c1c-41e6-9b60-567c72f004da`; two Ultima directories totaling about 141G; `v100_ksink` excluded by NOVASEQ evidence. |  | Inventory complete before deletion. |
| HUC-002 | Headnode/FSx | Delete Ultima analysis-results directories from `/fsx/analysis_results/ubuntu`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Operator explicitly confirmed deletion of the two listed Ultima directories. SSM command `5151e2b4-d644-45d5-995a-c1cea5ec2d73` ran as `ubuntu` on headnode `i-0e7639ff46f207ae7`; pre-delete validation reconfirmed both paths existed, both had `platform=ULTIMA`, `runids=602202-20260512-1805`, and sizes `70G` / `71G`; command ran `rm -rf --` on exactly those two paths; post-delete verification printed `DELETED` for both. `/fsx` changed from `7.9T used / 3.1T avail / 73%` at inventory to `6.3T used / 4.7T avail / 58%` after deletion. |  | Exact confirmed Ultima analysis-results directories are absent after deletion. |

## Prepared Destructive Command

Do not run until explicitly confirmed:

```bash
rm -rf -- \
  /fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z \
  /fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z
```

## Final Status

Completed at `2026-05-18T02:44:03Z` via SSM command `5151e2b4-d644-45d5-995a-c1cea5ec2d73`.

Deleted:

```text
/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z
/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z
```

Post-delete verification:

```text
DELETED /fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z
DELETED /fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z
```

FSx after deletion:

```text
Filesystem                Size  Used Avail Use% Mounted on
10.0.1.105@tcp:/ynjjzb4v   11T  6.3T  4.7T  58% /fsx
```
