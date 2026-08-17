# DYEC 18.0.25 release runbook

> **AWS credential notice.** This release used the overly-permissioned `lsmc` AWS profile. Josh Durham (@jdurham38) is actively porting the workflow to a tightly scoped IAM role; that work is underway.

This is the minimal corrective addendum to [RELASE-18.0.24-runbook.md](https://github.com/lsmc-bio/daylily-ephemeral-cluster/blob/18.0.24/docs/runbooks/18.0.24/RELASE-18.0.24-runbook.md).

- Keep the same pcand-18022 mount, no-delete FSx export, and interactive Ubuntu/tmux DayOA controller boundaries.
- `hiomr2_slim_kitchensink_mega` now passes `sentdhiomr2={"hg38_sentdhiomr2_chrms":"1-25"}` by default in live and dry commands.
- `inflection-bjuice-product-v0.9` remains the full 1-25 HIOMR2 kitchen-sink mega plus Inflection package; it defaults to all supplied ONT FASTQs and permits an explicit paired global ONT hour slice through `--dy-config use_fq_data_starting_hrs=<n>` and `--dy-config use_fq_data_up_to_hrs=<n+n>`.
- Both commands stay pinned to DayOA `15.0.14`.
- Do not delete FSx data. Fresh prerelease command-catalog tests are the next gate; no tests were run while cutting this tag.
