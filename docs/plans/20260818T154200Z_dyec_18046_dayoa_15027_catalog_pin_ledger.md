# DYEC 18.0.46 / DayOA 15.0.27 current-catalog pin release ledger

Controlling request: take the maximum published DYEC release, cut the next immutable DYEC version pinned to DayOA `15.0.27`, and set the mutable `current` command catalog to the same pin.

Release worktree: `/Users/jmajor/.codex-worktrees/dyec-release-18.0.46-dayoa-15.0.27` on `codex/release-18.0.46-dayoa-15.0.27`.

## Gate 0 baseline

- Remote strict numeric DYEC maximum: annotated `18.0.45`, tag object `b47934b43520cf2ccaad25ddf59eae35e6bdcf7d`, peeled commit `37b91419df841c4c019d1bfa52ae56fb1a2da4eb`.
- Remote strict numeric DayOA maximum: annotated `15.0.27`, tag object `672999034a0df08bdec43765be8204679693b818`, peeled commit `41c7f1c9b36fe6166337817133fc271923fc085f`.
- `18.0.46` is absent from remote DYEC tag refs before implementation. Existing tags will never be moved or overwritten.
- The clean release branch starts directly at `18.0.45`. `origin/main` is divergent from that immutable release line, so this release is published on its dedicated release branch and as an annotated tag; no unrelated-main merge is part of this request.
- The primary checkout has independent user changes and remains untouched. No cluster, headnode, workflow, export, or AWS state is changed by this release task.
- At the baseline, the current catalog already contains production pangenome command IDs `illumina_sentieon_pangenome_kitchensink` and `ultima_sentieon_pangenome_kitchensink`; both remain `hg38` activation workflows and will be preserved in the new frozen snapshot.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Release provenance | Verify maximum DYEC and requested DayOA annotated tags; prove `18.0.46` is unused | SUCCESS | contract_test | Gate 0 | release owner | Remote `ls-remote` tag refs and peeled commits recorded above |  | Safe next release version is `18.0.46`. |
| REL-001 | Catalog current | Pin catalog bootstrap default, all active top-level commands, and `dyec_builds.current` commands only to DayOA `15.0.27` | SUCCESS | feature_implementation | Gate 1 | release owner | Repository default ref, all 30 active commands, and all current-snapshot commands resolve exclusively to `15.0.27`. |  | No command shape changed beyond the pin. |
| REL-002 | Frozen snapshot | Copy the post-pin `current` catalog into immutable `dyec_builds.18.0.46`, retaining historical snapshots unchanged | SUCCESS | feature_implementation | Gate 1 | release owner | Parsed YAML proves `dyec_builds.18.0.46 == dyec_builds.current`; all prior snapshots, including `18.0.45`, are semantically unchanged. |  | New snapshot is frozen at the active `15.0.27` catalog state. |
| REL-003 | Pangenome catalog | Preserve both production pangenome kitchen-sink commands in `current` and `18.0.46` with `genome: hg38` and graph targets | SUCCESS | active_product_contract | Gate 1 | release owner | `illumina_sentieon_pangenome_kitchensink` retains `produce_sentpg_sr_snv_vcf`; `ultima_sentieon_pangenome_kitchensink` retains `produce_sentpg_ug_snv_vcf`; both are `prod`, `hg38`, and pin `15.0.27`. |  | No literal `pangenome` genome build was introduced. |
| REL-004 | Package parity | Keep canonical and packaged command catalogs byte-identical after the pin/snapshot update | SUCCESS | contract_test | Gate 1 | release owner | Canonical and packaged SHA-256: `fde790927b511c8bf5cc02966481426206900a22c9747bbe3dc40b9789f43bbe`. |  | Payload mirrors source byte-for-byte. |
| REL-005 | Operator contract | Update current release/pin docs and focused current-pin assertions without rewriting historical evidence | SUCCESS | contract_test | Gate 1 | release owner | Current README/operator docs and current-pin assertions now name `18.0.46` / `15.0.27`; historical plans were not rewritten. |  | Release-test filename and assertions now identify `18.0.46`. |
| REL-006 | Verification | Run focused catalog/parity/current-pin checks and `git diff --check` | SUCCESS | contract_test | Gate 5 | release owner | `pytest -q tests/test_release_18_0_46_pangenome_catalog.py tests/test_cli_docs_contract.py tests/test_repository_catalog_aliases.py` -> `22 passed in 151.99s`; post-commit `pytest -q tests/test_cli_docs_contract.py` -> `4 passed in 5.58s`; `git diff --check` passed. |  | Full repository suite was intentionally not run for this pin-only release. |
| REL-007 | Publication | Commit, push dedicated branch, create and push annotated `18.0.46` tag after final remote collision check | IN_PROGRESS | active_product_contract | Gate 5 | release owner | Candidate commit exists locally; final remote collision/tag/push checks pending. |  |  |

## Acceptance

The objective is complete only when `18.0.46` is an annotated remote DYEC tag whose catalog copies are byte-identical, whose `current` and frozen `18.0.46` command selections resolve exclusively to DayOA `15.0.27`, and whose snapshot retains both production pangenome workflows. No workflow execution is in scope.
