# Production catalog launch control ledger

Controlling request: run the ILMN, ONT, and Ultima SeqQC catalog commands; the
ILMN, ONT, Ultima, and CG solo kitchen-sink catalog commands; and the HIOMR2
kitchen-sink mega + Inflection analytical command, using DYEC 16.1.83 and
DayOA 13.4.31 on the available cluster.

## Gate 0 — inventory freeze

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `codex/catalog-16.1.81` (ahead of origin by one); pre-existing untracked
  artifacts were present and are not owned by this ledger.
- Local executable: `dyec --version` -> `Daylily Ephemeral Cluster 16.1.83`.
- Headnode executable before refresh: `16.1.74.dev2+gc3e1dac06`; its `dyec
  analysis` command was present, including `visit`, `guard`, and `lock`.
- Headnode refresh: the first bootstrap attempt failed because it selected
  legacy public-clone authentication. A subsequent deploy-key refresh
  selected the configured self-pin (`16.1.82`) rather than the installed local
  DYEC (`16.1.83`) and left the headnode reporting `16.1.44`. No further
  headnode change was made after that unexpected version result.
- Authoritative DayOA Git remote: the highest numeric tag is annotated
  `13.4.31` (`b54a6b3d4893…`, peeled commit `a6a7cd493eec…`). Every eventual
  launch must pass this exact tag rather than trust the headnode default.
- Available cluster: `prod-cand-260809`, profile `lsmc`, region `us-west-2`,
  `UPDATE_COMPLETE`, headnode configured.
- Catalog inspection: all eight requested command IDs resolve to git tag
  `13.4.31` in the current catalog.
- Existing read-only run mounts: ILMN
  `bjuicepreval-20260618-ilmn`, ONT
  `bjuicepreval-20260615-ont-set4-fc1`, and Ultima
  `ultima-602202-20260512` are `AVAILABLE`.
- CG fixture: `complete-genomics-solo-six-manifest-v1` is `AVAILABLE`; its
  checked-in `analysis_units.tsv` specifies `SUBSAMPLE_PCT=0.05`.
- Existing unrelated CG controller
  `solo-cg-sqjx8366-30x-13430-20260811-r1-live` is terminal `SUCCEEDED` on
  DayOA 13.4.30. It is not this requested 13.4.31 launch and was not changed.
- No workflow controller was launched by this task.

## Execution ledger

| ID | Requirement | Status | Gate | Evidence / blocker |
|---|---|---|---|---|
| G0-001 | Record execution baseline | SUCCESS | Gate 0 | Inventory above; cluster, mounts, catalog tags, and pre-existing repository state captured before launch. |
| HN-001 | Refresh headnode DYEC without downgrade | BLOCKED | Headnode toolchain | The supported deploy-key refresh followed the configured self-pin (`16.1.82`) instead of the installed local DYEC (`16.1.83`) and the headnode then reported `16.1.44`. Do not retry until the installer accepts and verifies an operator-selected release tag. |
| HN-002 | Add explicit DYEC headnode version selection | SUCCESS | Headnode toolchain | `headnode configure`, `headnode configure-dragen`, and `daylily_cfg_headnode.py` now accept `--dyec-version`; it requires the DYEC deploy key, rejects a non-release/mismatched ref, clones the exact tag, and fails unless remote `dyec --version` exactly equals the requested version. Focused unit/CLI/script tests: 24 passed. |
| HN-003 | Replace explicit/static selection with the running installed release | SUCCESS | Headnode toolchain | The superseding `16.1.85` candidate removes both global YAML self-pin keys and the headnode `--dyec-version` override. Configure derives the exact release reported by the running DYEC, checks out `refs/tags/<running-version>`, and always verifies the same remote `dyec --version`; the release-specific gate passed 681 tests. |
| REL-001 | Publish corrected headnode-configure double release | NO_LONGER_NEEDED | Release policy | The explicit-version fix merged in PR #95 and is preserved by annotated tag `16.1.84` at `cd41cd510c6ca60073006b3ed79f3251899db298`. The double-release/self-pin design was superseded by the owner's single-release installed-version contract; no pushed tag was moved. |
| REL-002 | Publish the superseding prod-candidate release train | SUCCESS | Release policy | DayOA annotated `13.4.33` peels to `56208632627ccff4c1fb2b2525900e68de59ec12`; DYEC annotated `16.1.85` peels to `fd1b583b73ccc22e3c3589357e4d3b09c8502d6a`. Both `prod-candidate-260911` branches and tags were pushed and verified. DYEC contains the DayOA pin, catalog-v5 `current` default, exact `16.1.85` snapshot, and installed-version headnode contract. |
| PCL-001 | ILMN SeqQC (`illumina_run_qc`) | BLOCKED | DayOA execution contract | The catalog's exact command begins `bin/day_run`, but the controlling DayOA contract permits workflow execution only through `dy-r` in a persistent ubuntu tmux session. The input run is also not specified among the available ILMN mount and the catalog's historical profile. |
| PCL-002 | ONT SeqQC (`ont_run_qc`) | BLOCKED | DayOA execution contract | Same `bin/day_run`/`dy-r` conflict; select the exact mounted ONT run before a launch. |
| PCL-003 | Ultima SeqQC (`ultima_run_qc`) | BLOCKED | DayOA execution contract | Same `bin/day_run`/`dy-r` conflict; select the exact mounted Ultima run before a launch. |
| PCL-004 | ILMN solo kitchen sink (`illumina_hg002_kitchensink_multiqc`) | BLOCKED | DayOA execution contract | Exact catalog command begins `bin/day_run`; executing it would violate the current `dy-r`-only contract. Its prepared slim six-manifest exists locally. |
| PCL-005 | ONT solo kitchen sink (`ont_snv_alignstats_kitchensink`) | BLOCKED | DayOA execution contract | Exact catalog command begins `bin/day_run`; executing it would violate the current `dy-r`-only contract. Its prepared slim six-manifest exists locally. |
| PCL-006 | Ultima solo kitchen sink (`ultima_snv_alignstats_kitchensink`) | BLOCKED | DayOA execution contract | Exact catalog command begins `bin/day_run`; executing it would violate the current `dy-r`-only contract. Its prepared slim six-manifest exists locally. |
| PCL-007 | CG solo kitchen sink (`complete_genomics_cg_snv_concordance`) | BLOCKED | DayOA execution contract | Exact catalog command begins `bin/day_run`; executing it would violate the current `dy-r`-only contract. The available mounted fixture supplies the requested `0.05` subsample setting. |
| PCL-008 | HIOMR2 mega + Inflection (`hiomr2_slim_kitchensink_mega_inflection_analytical`) | BLOCKED | Production configuration | This is the only requested catalog command that uses `dy-r`; however its catalog default is the documented two-contig validation scope `19-20`. Full production requires the explicit `1-25` override, and no Slurm cost center was supplied. |

## Terminal-state report

The production execution rows are terminal, but the overall objective is not
complete: no new controller was started. The superseding DayOA/DYEC release
train is published. Unblock the production launch by
approving the catalog `bin/day_run` command shape as an exception to the local
`dy-r`-only execution contract, selecting one mounted run per SeqQC platform,
and providing the cost center. For HIOMR2, the approved launch will set
`sentdhiomr2.hg38_sentdhiomr2_chrms=1-25` rather than the catalog's documented
`19-20` validation default.
