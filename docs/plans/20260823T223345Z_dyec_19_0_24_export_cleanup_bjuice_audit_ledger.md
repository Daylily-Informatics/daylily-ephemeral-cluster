# DYEC 19.0.24 DayOA 16.0.6 pin, export, cleanup, and Bjuice accessibility ledger

Controlling request: release DYEC with DayOA `16.0.6` internally and in the
current command catalog; update the local DYEC checkout; export Bundle 1b and
all remaining eligible `pclu-18045` analysis roots; obtain exact-root cleanup
approval after successful receipts; inventory DRA mounts; and audit the complete
Bjuice workbook against currently accessible ILMN/ONT inputs and FSx capacity.

Ledger path:
`docs/plans/20260823T223345Z_dyec_19_0_24_export_cleanup_bjuice_audit_ledger.md`

## Gate 0: inventory freeze

- Private DYEC worktree:
  `/Users/jmajor/.codex-worktrees/dyec-release-19.0.24-dayoa-16.0.6`
- Branch: `codex/release-19.0.24-dayoa-16.0.6`.
- Baseline: annotated DYEC `19.0.23`, tag object
  `7f4e1bd1de4b85636a279b8d40f0a0e1bb57f313`, peeled commit
  `e33cc9f6c4ba1cb4305980e21cf3d29a7ea74050`.
- `19.0.23` is a merge tag whose checked-in `CURRENT_DYEC_BUILD` and latest
  immutable catalog snapshot are both `19.0.22`; the new snapshot must preserve
  that historical `19.0.22` data unchanged.
- DayOA dependency: annotated `16.0.6`, tag object
  `65a972e4293a5b2a728eca3dfc4793bbbd545ab3`, peeled commit
  `063504036cac9cc9cc10d88453b5f0d437b6a0dc`.
- Shared checkout `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` is
  detached and has unrelated untracked content; it is excluded from source
  edits until the released tag is installed.
- Cluster export target: `pclu-18045`, profile `lsmc`, region `us-west-2`.
- Bundle 1b root:
  `/fsx/analysis_results/pclu-18045/pclu18045_bundle1b_bjuice_ifx_19011_16004_20260821t081200z`.
- FSx deletion is a separate destructive gate. No root is eligible for cleanup
  until its full-root export receipt has success/complete/SUCCEEDED evidence,
  its destination is listed exactly, and the human gives a second confirmation.
- Complete Bjuice source workbook:
  `/Users/jmajor/Downloads/Betelgeuse Validation - LAB.xlsx`; its checked-in
  guidance has five bundle rows and 131 paired hybrid AUs.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DYEC source/catalog | Create `19.0.24`: retarget active DayOA default and active commands to `16.0.6`, and add an immutable `dyec_builds.19.0.24` snapshot without altering historical snapshots. | COMPLETE | feature_implementation | Gate 1 | Codex | Active catalog has 34 `16.0.6` commands and zero active `16.0.5` commands; source/payload catalogs byte-match. Focused pin/registry tests: 5 passed. Python compile, YAML parse, and `git diff --check` passed. | The broad registry run had 14 pre-existing unrelated failures, reproduced unchanged at pristine `19.0.23`. | Ready to commit/tag. |
| REL-002 | DYEC publication/install | Commit, push, annotated-tag the new DYEC release, then update `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` to that exact release. | OPEN | feature_implementation | Gate 5 | Codex | Pending source validation and release commit. |  |  |
| EXP-001 | `pclu-18045` analysis roots | Inventory every `/fsx/analysis_results/**` root, classify existing export evidence, and execute no-delete DYEC exports only for roots that remain unexported and terminal. | IN_PROGRESS | active_product_contract | Gate 5 | Codex | Bundle 1b current footprint was 4.77 TiB; current FSx was 87% used before this request. |  |  |
| DEL-001 | `pclu-18045` FSx cleanup | Delete only the exact successfully exported roots through `dyec exports cleanup --confirm-fsx-delete` after a second explicit approval names the root list and matching S3 destinations. | BLOCKED | legitimate_safety_handling | Gate 5 | Codex | Initial user request is the required first approval. | Exact roots/destinations and successful export receipts are not yet known. | Await second explicit confirmation after the receipt-bound deletion list is presented. |
| MNT-001 | `pclu-18045` DRA inventory | Report every current DRA mount ID, lifecycle, source S3 URI, and mounted `/fsx/**` path. | IN_PROGRESS | active_product_contract | Gate 0 | Codex | Pending live DYEC inventory. |  |  |
| BJV-001 | Bjuice workbook accessibility/capacity | For each complete-set bundle row, verify currently mounted ILMN and ONT path accessibility and compare the complete-set source footprint with post-export FSx capacity. | IN_PROGRESS | active_product_contract | Gate 0 | Codex | Workbook/guidance defines Bundle 1a, 1b, 2, 3, and 4 source pairs; historical inventory is not treated as current mount proof. |  |  |

## Final report

All rows terminal: no

Objective complete: no
