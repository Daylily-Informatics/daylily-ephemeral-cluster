# Bjuice20 Manual Export Repair Completion

- Completed at: `2026-07-20T02:59:24Z`
- Failed FSx task repaired: `task-002d8e282dc07dff6`
- Failed-object report rows: `36`
- Objects copied and validated: `36`
- Copy or validation failures: `0`
- Total copied bytes: `285,511,373,643`
- Source analysis root was not modified.
- No S3 object was overwritten or deleted.

The 36 missing package objects were 18 short-read CRAMs and their 18 CRAI
indexes. Each package path was proven to be the second hard link to an exact
source artifact in the same FSx analysis root. The source inode had link count
two, equal byte size at both paths, and clean `exists archived` HSM state.

The current destination prefix did not contain the source-side hard-link paths,
so the repair used the immediately preceding immutable S3 export of the same
analysis root as the server-side copy source. Before copying, all 36 source S3
objects were required to match their current FSx inode byte sizes and all 36
destination keys were required to be absent. Every destination object was then
checked for matching byte size and a stored S3 SHA-256 checksum.

Destination prefix:

`s3://lsmc-dayoa-analysis-results-usw2/validation/inflight_pr53_recovery_20260720T011608Z/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/`

Evidence:

- `s3://lsmc-dayoa-analysis-results-usw2/validation/inflight_pr53_recovery_20260720T011608Z/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/_daylily_monitor/fsx-export/manual-copy-20260720T023359Z/hardlink_mapping.tsv`
- `s3://lsmc-dayoa-analysis-results-usw2/validation/inflight_pr53_recovery_20260720T011608Z/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/_daylily_monitor/fsx-export/manual-copy-20260720T023359Z/manual_copy_receipt.tsv`
- `s3://lsmc-dayoa-analysis-results-usw2/validation/inflight_pr53_recovery_20260720T011608Z/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/_daylily_monitor/fsx-export/manual-copy-20260720T023359Z/summary.json`
