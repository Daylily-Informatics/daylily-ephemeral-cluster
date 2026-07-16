# ifx-reworkB Betelgeuse DRA And HG003 1x Hybrid Ledger

Stamp: `20260708T220626Z`

Ledger: `docs/plans/20260708T220626Z_ifx_reworkB_betelgeuse_dra_hg003_1x_hybrid_ledger.md`

Artifacts: `docs/plans/20260708T220626Z_ifx_reworkB_betelgeuse_dra_hg003_1x_hybrid/`

Cluster/profile/region: `ifx-reworkB` / `lsmc` / `us-west-2`

DayOA tag/ref for new controller: `10.0.72`

New analysis/session: `ifx_reworkb_hybrid_hg003_1x_20260708t220626z`

Requested live work:
- Start read-only DRA staging for the Betelgeuse pre-validation ILMN/ONT run directories.
- Start exactly one slim-data HG003 1x hybrid controller with `-p -k -j 400`.
- Poll the hybrid controller every 5 minutes and report status.

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Existing dirty state before this ledger: spot-price source/test edits plus earlier plan artifacts from the current thread.
- Previous controller: `ifx_reworkb_hybrid_ilmn_ont_snv_nodra_20260708t214413z` completed at `2026-07-08T21:55:24Z` with `exit_code=1`.
- Previous controller root cause: Slurm job submission rejected project/cost-center `ifx-reworkB` because the cost-center registry lookup returned empty JSON.
- Gate 0 live state: `dyec --json mounts list --cluster ifx-reworkB` returned `{"mounts": []}`; `dyec headnode jobs --cluster ifx-reworkB` returned only the header.
- Active cost center selected for new controller: `cmdcat-103-all-20260707`, status `active`, allowed user `ubuntu`, monthly cap `5000`.

## Input/DRA Set

| Mount ID | Platform | S3 URI | Source Evidence |
|---|---|---|---|
| `20260615_ONT_Set3-FC1` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set3-FC1/` | July 4 hybrid ledger and July 5 DRA inventory. |
| `20260615_ONT_Set3-FC2` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set3-FC2/` | July 4 hybrid ledger and July 5 DRA inventory. |
| `20260615_ONT_Set3-FC3` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set3-FC3/` | July 4 hybrid ledger; original association was `dra-0e3db422b0eec8d0d` on `jemx3`. |
| `20260615_ONT_Set4-FC1` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC1/` | July 4 hybrid ledger and July 5 DRA inventory. |
| `20260615_ONT_Set4-FC2` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC2/` | July 4 hybrid ledger and July 5 DRA inventory. |
| `20260615_ONT_Set4-FC3` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC3/` | July 4 hybrid ledger and July 5 DRA inventory. |
| `20260618_LH01106_0011_A23MFMCLT3` | ILMN | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/` | July 8 DRAGEN DRA ledger; headnode checks found expected BCLConvert FASTQs. |

## Control Rows

| ID | Area | Requirement | Status | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|
| DRA-001 | DYEC DRA | Start read-only DRA mounts for all Betelgeuse pre-validation ONT/ILMN run directories on `ifx-reworkB`. | SUCCESS | Seven `dyec --json mounts create ... --read-only --no-wait` calls succeeded at `2026-07-08T22:07:58Z`-`2026-07-08T22:08:00Z`; associations: `dra-0b67e9a6e45f65aac`, `dra-0f5317843095d728f`, `dra-0e922dfd7eb2fdfd5`, `dra-0e14bebab253956d1`, `dra-062e2cd4cb5a2ba1a`, `dra-053f2d574d4061ad6`, `dra-0d56107343cff175d`; `dyec --json mounts list` shows all seven `CREATING`. |  | DRA staging started asynchronously; availability remains under `MON-001`. |
| CFG-001 | Slim-data manifest | Generate one-row HG003 1x pass-through samples/units config without creating a staged-prefix DRA. | SUCCESS | `dyec samples stage ... --config-only --config-dir docs/plans/20260708T220626Z_ifx_reworkB_betelgeuse_dra_hg003_1x_hybrid/config` -> precheck `rows checked=1`, `samples checked=1`, `source objects checked=22`, `concordance directories checked=1`; generated `20260708T220830Z_150a724c_samples.tsv` and `20260708T220830Z_150a724c_units.tsv`. |  | Config-only path did not create a staged-prefix DRA. |
| RUN-001 | Hybrid controller | Launch exactly one new HG003 1x hybrid controller with `-p -k -j 400`, using a valid cost center. | SUCCESS | `dyec workflow launch --cluster ifx-reworkB --analysis-id ifx_reworkb_hybrid_hg003_1x_20260708t220626z --session-name ifx_reworkb_hybrid_hg003_1x_20260708t220626z --git-tag 10.0.72 --genome hg38_broad --project cmdcat-103-all-20260707 --strict-project-check --samples-file ...150a724c_samples.tsv --units-file ...150a724c_units.tsv --dy-command <lock-wrapped dy-r command>` succeeded; tmux session created at `2026-07-08T22:10:48Z`. |  | One controller started; launch log shows budget lookup succeeded and analysis-root write lock acquired before `dy-r`. |
| MON-001 | Monitoring | Poll the controller and mounts at 5-minute cadence and report back. | IN_PROGRESS | Immediate post-launch poll: workflow status active with `exit_code=null`, `completed_at=null`; Slurm queue empty at first snapshot; all seven DRA mounts `CREATING`. Five-minute poll at `2026-07-08T22:16:38Z`: workflow status still active with `exit_code=null`; visible controller log reached `5 of 746 steps`; Slurm jobs `2` `sentdhiomr_sr_align` and `3` `sentdhiomr_call_svs` pending at 96 CPUs / 300000M; all seven DRA mounts still `CREATING`. |  | Controller and DRA staging are in progress; no Slurm intervention taken. |
