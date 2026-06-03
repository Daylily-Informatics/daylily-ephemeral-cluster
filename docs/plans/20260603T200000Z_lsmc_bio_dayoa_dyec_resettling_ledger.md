# lsmc-bio DayOA/DYEC Fork Resettling Ledger

Created: 2026-06-03T20:00:00Z

## Objective

Make `lsmc-bio/daylily-omics-analysis` and `lsmc-bio/daylily-ephemeral-cluster`
the canonical repos for these two projects, without merging upstream fork
histories, without publishing anything from lsmc-bio to PyPI, and with
regression guards preventing active DayOA/DYEC deployment paths from drifting
back to `Daylily-Informatics`.

## Gate 0 Inventory

| Surface | State |
| --- | --- |
| lsmc-bio DayOA main before replacement | `e00600241726585980f7e7c7e60d3ee14c9d2e6a` |
| Daylily-Informatics DayOA main blessed source | `aed7c0078339e79459f4db3e30d7e89438467e19`, tag `5.0.0` |
| lsmc-bio DYEC main before replacement | `93e37053b79a3627b32f5bb6314e2c5ef7120a17` |
| Daylily-Informatics DYEC main blessed source | `26aacae038ac5e21b9de49efb43c3fc47fdacf29`, tag `7.0.0` |
| lsmc-bio Ursa main | `cebdeb74bed7728cb4081452794dba1fec57d707` |
| Daylily-Informatics Ursa main | `bff396e033eae29e20f768c2fce24eb56d0385ff` |
| lsmc-bio Bloom main | `cf27cef2608429d77843e646380ed81780ce5848` |
| Daylily-Informatics Bloom main | `587f0133d7f83e29bbcaadada464749d4a548a66` |
| lsmc-bio DayOA target checkout | `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, cloned fresh, no stash needed |
| lsmc-bio DYEC target checkout | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, cloned fresh, no stash needed |
| lsmc-bio Ursa checkout | `/Users/jmajor/projects/lsmc/daylily-ursa`, dirty and behind before follow-up; existing dirt not overwritten |
| lsmc-bio Bloom checkout | missing locally; remote fork exists |
| Release tag availability | `5.0.1` and `7.0.1` absent on lsmc-bio remotes before release work |
| PyPI policy | No `twup`, Twine upload, or PyPI publication for lsmc-bio DayOA/DYEC |

## Execution Ledger

| Gate | Agent | Item | Status | Evidence | Blocker / next action |
| --- | --- | --- | --- | --- | --- |
| 1 | Agent 2 | Reset lsmc-bio DayOA main to blessed Daylily `5.0.0` source | SUCCESS | `git reset --hard aed7c0078339e79459f4db3e30d7e89438467e19`; `git push --force-with-lease origin main`; GitHub recorded branch-protection bypass |  |
| 1 | Agent 2 | Reset lsmc-bio DYEC main to blessed Daylily `7.0.0` source | SUCCESS | `git reset --hard 26aacae038ac5e21b9de49efb43c3fc47fdacf29`; `git push --force-with-lease origin main`; GitHub recorded branch-protection bypass |  |
| 2 | Agent 3 | Rewire active DayOA surfaces to lsmc-bio | SUCCESS | Commit `29211abf9eec106b5caeb439425e3b84730b4f5e`; active config, README/tool docs, setup-test clone URLs, launch helper, help text, and MultiQC provenance strings point to `lsmc-bio` |  |
| 2 | Agent 4 | Rewire active DYEC surfaces to lsmc-bio | SUCCESS | Commit `66838de08ce4f742a880aab0964b6168a7deedbb`; self config, payload self config, command catalog, payload catalog, bootstrap clone URLs, README badges, create-cluster default, tests, and DayOA GitHub dependency point to `lsmc-bio` |  |
| 3 | Agent 6 | Add DayOA active-reference guard | SUCCESS | `tests/test_lsmc_bio_fork_contract.py`; `python -m pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_tool_catalog_docs.py tests/test_shell_wrapper_contracts.py` -> `22 passed` |  |
| 3 | Agent 6 | Add DYEC active-reference guard | SUCCESS | `tests/test_lsmc_bio_fork_contract.py`; `python -m pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_packaged_defaults.py tests/test_workflow.py::TestConfigureHeadnode::test_repo_checkout_uses_published_detached_tag` -> `10 passed` |  |
| 4 | Agent 5 | DayOA GitHub-only release `5.0.1` | SUCCESS | Annotated tag `5.0.1` points to `29211abf9eec106b5caeb439425e3b84730b4f5e`; `git cat-file -t 5.0.1` -> `tag`; release URL `https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/5.0.1`; local `python -m build` completed | No Twine, `twup`, or PyPI upload command run |
| 4 | Agent 5 | DYEC GitHub-only release `7.0.1` | SUCCESS | Annotated tag `7.0.1` points to `66838de08ce4f742a880aab0964b6168a7deedbb`; `git cat-file -t 7.0.1` -> `tag`; release URL `https://github.com/lsmc-bio/daylily-ephemeral-cluster/releases/tag/7.0.1`; local `python -m build` completed | No Twine, `twup`, or PyPI upload command run |
| 5 | Agent 7 | Ursa follow-up pin update | SUCCESS | Used clean temp clone `/tmp/ursa-lsmc-dyec701.8U5VVV/daylily-ursa`; branch `codex/pin-lsmc-dyec-dayoa-20260603`; commit `d0e8448e694ef0ecfe1e6f60e6386a485fa61340`; PR `https://github.com/lsmc-bio/daylily-ursa/pull/14`; activated env installed DYEC `7.0.1` and DayOA `5.0.1` from lsmc-bio GitHub tags | Existing dirty local Ursa checkout left untouched |
| 5 | Agent 7 | Bloom fork check | SUCCESS | `gh repo view lsmc-bio/bloom` succeeded; local checkout absent | No immediate Bloom pin update found yet |
| 6 | Agent 8 | Validation and acceptance | SUCCESS | DayOA: `git diff --check`, guard/docs/wrapper tests, `python -m build`; DYEC: `git diff --check`, TOML/YAML parse, guard/payload/workflow tests, `python -m build`; Ursa: `git diff --check`, TOML/JSON/YAML parse, `source ./activate lsmcfrk && python -m pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_activation_metadata.py tests/test_daylily_ec_runner.py tests/test_cluster_headnode_diagnostics.py tests/test_admin_gui_and_cluster_routes.py` -> `47 passed, 90 warnings` | All ledger rows terminal |

## Notes

- lsmc-bio fork histories were replaced; no merge commits were used.
- GitHub tag namespaces are repo-local, so `5.0.1` and `7.0.1` can be used in
  lsmc-bio without moving Daylily-Informatics tags.
- Local upstream tag imports may create local tag-name collisions; only explicit
  lsmc-bio release tags are pushed.
- `daylily-omics-analysis` `5.0.1` and `daylily-ephemeral-cluster` `7.0.1`
  were built locally only for validation. No PyPI upload path was executed.
- `daylily-ephemeral-cluster` release tag `7.0.1` remains at release commit
  `66838de08ce4f742a880aab0964b6168a7deedbb`; this ledger closeout is committed
  after the release tag on `main` and does not move `7.0.1`.
