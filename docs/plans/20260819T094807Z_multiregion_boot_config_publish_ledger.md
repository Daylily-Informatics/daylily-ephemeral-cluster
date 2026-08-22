# Multi-Region Immutable Boot-Config Publish Ledger

Date: 2026-08-19

## Objective

Publish the current immutable DYEC boot-config bundle, including the pinned
Ubuntu `post_install_ubuntu_combined.sh`, to each existing requested
`lsmc-dayoa-references*` bucket in `us-west-2`, `us-east-1`, `us-west-1`, and
`us-east-2`.

## Gate 0: Inventory Freeze

- Source checkout: `39cd316741207623ead31f49f50d48c39fd11640`.
- Deterministic bundle release suffix:
  `releases/sha256-7c3ef64e47e5c2c083d80e8815793ea07a72905ab86909c03e6aea2b03285b2e`.
- Ubuntu script source SHA-256:
  `f9b2891e9ea83cbb07570dcf48ae01c906cad09f86927fa3c3dde391f116bbb1`.
- Existing requested reference buckets discovered read-only:
  `lsmc-dayoa-references-usw2` in `us-west-2` and
  `lsmc-dayoa-references-use1` in `us-east-1` (AWS represents that region as
  a null location constraint).
- No matching `lsmc-dayoa-references*` bucket exists in `us-west-1` or
  `us-east-2`.
- The sole publisher is
  `daylily_ec.workflow.create_cluster.publish_cluster_boot_config`; it writes
  only the exact content-addressed prefix with `IfNoneMatch="*"` and verifies
  content hashes afterward. No raw S3 file copy, overwrite, cluster create,
  deletion, cache change, or budget action is in scope.

## Execution Rows

| ID | Category | Status | Evidence / terminal note |
| --- | --- | --- | --- |
| G0 | config_or_startup_contract | SUCCESS | Inventory frozen as recorded above. |
| R1 | config_or_startup_contract | SUCCESS | `lsmc-dayoa-references-usw2` already contained all seven objects at the exact release prefix; each `daylily-sha256` metadata value matches source. |
| R2 | config_or_startup_contract | SUCCESS | Published and byte-for-byte read-back verified all seven objects in `lsmc-dayoa-references-use1` at the exact release prefix. |
| R3 | not_applicable_after_inspection | NO_LONGER_NEEDED | No matching requested bucket exists in `us-west-1`; no object action is needed. |
| R4 | not_applicable_after_inspection | NO_LONGER_NEEDED | No matching requested bucket exists in `us-east-2`; no object action is needed. |
| R5 | active_product_contract | SUCCESS | Commit `d8a3e223e14b7e0474c45807678bbce0af7d0b5d` fast-forwarded `origin/main`; no force push. |

## Acceptance

All rows must be terminal. Each existing target bucket must contain the same
content-addressed release bundle, and every uploaded object must read back with
the source body SHA-256 and matching `daylily-sha256` metadata.

## Completion

All rows are terminal and successful. A final read-back audit verified all
seven objects in both existing target buckets against source-body and metadata
SHA-256 values. No matching bucket existed in the two remaining requested
regions, and no cluster or existing S3 object was altered.
