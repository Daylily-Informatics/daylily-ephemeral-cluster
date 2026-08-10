## Control Ledger

Controlling plan: user request in this task to rerun VEP sharded by chromosome for chr1--chr25, merge correctly, and download the validated final artifact.

Ledger path: `docs/plans/20260810T164600Z_johnmajor_vep_chr1_25_retry_ledger.md`

### Gate 0 baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/pin-dayoa-13.4.10-16.1.45`; existing user changes include `AGENTS.md` and numerous untracked plans/artifacts. This ledger is additive and does not alter those files.
- Failed predecessor: Slurm `562`, `FAILED` exit `1:0`, elapsed `03:03:33`, remote root `/fsx/tmp/vep_johnmajor_sqjx8366_20260810T132200Z`.
- Input: existing remote `input.vcf.gz`, 12,944,448 source records. Retry scope is only chromosomes `1` through `25`; contigs outside that scope are intentionally excluded.
- Live boundary: submission of a new VEP Slurm job is explicitly authorized by the user. No Slurm intervention on the failed job will occur.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| VEP-001 | Input scope | Partition the existing VCF into chr1--chr25 shards and account for scoped input records. | IN_PROGRESS | feature_implementation | Gate 0 | `/root` | Remote input at predecessor root; failed predecessor logged unsupported decoy contigs. |  |  |
| VEP-002 | Annotation | Annotate each chromosome shard using the established VEP 114 GRCh38 cache/container contract. | OPEN | feature_implementation | Gate 0 | `/root` | Predecessor job 562 used VEP 114 and failed before final validation. |  |  |
| VEP-003 | Merge | Merge successful chromosome outputs in chromosome order, retaining exactly one CSQ header and a tabix index. | OPEN | feature_implementation | Gate 0 | `/root` | User explicitly requested correct merge. |  |  |
| VEP-004 | Validation | Verify scoped record equality, header cardinality, compression/index integrity, and SHA-256 manifest. | OPEN | contract_test | Gate 5 | `/root` | Required before delivery. |  |  |
| VEP-005 | Delivery | Download only validated final VCF, index, summary, and manifest to `/Users/jmajor/Downloads`. | OPEN | feature_implementation | Gate 5 | `/root` | User explicitly requested final download. |  |  |
