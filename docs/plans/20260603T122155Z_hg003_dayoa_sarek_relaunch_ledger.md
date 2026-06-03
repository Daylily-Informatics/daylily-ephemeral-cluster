# HG003 DayOA And Sarek Relaunch Ledger

Created: 2026-06-03T12:21:55Z

Objective: relaunch both HG003 5x benchmark arms on `dyec5128` after the DayOA `run:` plus `benchmark:` fix landed in DayOA `2.0.40`, and use the documented direct Nextflow path for `daylily-sarek`.

Cluster: `dyec5128`
Region/profile: `us-west-2` / `lsmc`
Executing entity: `ubuntu`

| ID | Step | Status | Evidence |
|---|---|---|---|
| G0-001 | Read current Sarek runbook and DYEC catalog. | SUCCESS | `docs/running_nextflow_pipes.md`; catalog row `daylily-sarek` default ref `0.7.379`; DayOA command `illumina_snv_alignstats` supports `--git-tag` override. |
| G0-002 | Confirm prior DayOA benchmark terminal state. | SUCCESS | Session `dyec5128_hg003_5x_ilmn_snv_20260603T110935Z` completed `2026-06-03T11:45:09Z`, `exit_code=1`, failure in `run:` + `benchmark:` path. |
| DYOA-001 | Launch new DayOA `2.0.40` HG003 5x arm. | PENDING |  |
| SAREK-001 | Preflight/install pinned Sarek Nextflow runtime. | PENDING |  |
| SAREK-002 | Clone/patch/launch `daylily-sarek` HG003 5x arm. | PENDING |  |
| MON-001 | Capture initial status for both arms. | PENDING |  |

