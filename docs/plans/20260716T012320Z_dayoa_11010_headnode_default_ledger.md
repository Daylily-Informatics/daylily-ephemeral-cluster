# DayOA 11.0.10 Headnode Default Ledger

Controlling request: publish the exact-identity DayOA correction and make the
configured `ifx-p2-1000-120-0715` headnode `day-clone` default resolve to that
new DayOA version without restarting the paused analysis controller.

Ledger path: `docs/plans/20260716T012320Z_dayoa_11010_headnode_default_ledger.md`

## Gate 0 Baseline

- Repo: `daylily-ephemeral-cluster`
- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-main-release-10315-20260716`
- Branch: `codex/dyec-main-release-10315`, fast-forwarded to `origin/main`
  commit `0e400f0ff905f5f69055cb7f0d222520916490cf` before edits.
- Existing source/payload DayOA default and HIOMRS pins: `11.0.9`.
- Existing DYEC self pin: `10.3.15`.
- Target releases: DayOA `11.0.10`; DYEC `10.3.16`.
- Live scope: install source-owned headnode tools/catalog on cluster
  `ifx-p2-1000-120-0715`; do not restart `dy-r`, alter Slurm, or delete data.

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| DHD-001 | Catalog | Set source and payload `daylily-omics-analysis.default_ref` to `11.0.10`. | SUCCESS | config_or_startup_contract | Gate 2 | Commit `1f498f30`; catalog and payload match; focused tests passed. | DayOA default updated without a mutable-only headnode patch. |
| DHD-002 | HIOMRS catalog | Pin both Sentieon HIOMRS command rows to DayOA `11.0.10`. | SUCCESS | config_or_startup_contract | Gate 2 | Commit `1f498f30`; both catalog rows and payload rows use `11.0.10`. | Exact HIOMRS commands now select the released DayOA correction. |
| DHD-003 | DYEC release | Advance source/payload self pins to `10.3.16` in a separate commit and push an annotated tag. | SUCCESS | feature_implementation | Gate 5 | Catalog commit `1f498f30`; self-pin commit `946c3053528d5cd16ad79a673dae93af4e907c9b`; full suite `1542 passed, 11 skipped`; feature, `sentieon-single`, and `main` pushed; annotated `10.3.16` tag pushed. | DYEC source and packaged payload are released at the same pin. |
| DHD-004 | Headnode | Install the exact DYEC release and verify `day-clone` default/auth resolves DayOA `11.0.10`. | SUCCESS | config_or_startup_contract | Gate 5 | First configure attempt failed git rc 128 because no DYEC deploy-key reference was supplied; read-only `git ls-remote` confirmed `Permission denied (publickey)`. Retry with the exact cluster-YAML DYEC and DayOA Secret ARNs succeeded. Headnode `HEAD=946c3053`, annotated `10.3.16`; catalog default and both HIOMRS pins are `11.0.10`; `day-clone --check-auth` passed. | Supported SSM configurator installed the source-owned release; no mutable-only patch remains. |
| DHD-005 | Safety | Keep the paused analysis controller stopped and leave Slurm/data untouched. | SUCCESS | legitimate_safety_handling | Gate 5 | Exact `squeue` format returned header only; `ps` found no `dy-r`, `day_run`, or Snakemake process after configuration. | No workflow restart, Slurm change, or analysis-data mutation occurred. |

## Final Report

All rows terminal: yes.

Objective complete: yes. DYEC `10.3.16` owns the DayOA `11.0.10` default and
HIOMRS pins, and the target headnode has the exact release installed.
