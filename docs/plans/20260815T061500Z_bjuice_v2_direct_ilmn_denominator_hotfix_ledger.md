# Bjuice v2 direct Illumina denominator hotfix ledger

## Baseline

- Failed analysis: `prod-cand-1703-hg002-bjuice-v2-retargeted-srfix-20260815T055000Z` on `prod-cand-1703` (`us-west-2`, profile `lsmc`).
- Verified direct full-prevalence Illumina denominator: `43.73x`.
- The failed retarget plan supplied fractions calculated as `prior_subsample_pct * target / prior_measured_coverage`. The prior controller had not applied its requested Illumina fraction, so this produced sparse CRAMs (for example `p5xp5=0.000669426130`) and TIDDIT failed with `ValueError: cannot convert float NaN to integer`.

## Control rows

| ID | Requirement | State | Evidence |
| --- | --- | --- | --- |
| FIX-001 | Retarget-plan fractions must use the verified direct denominator and must not be overridden by prior observations. | COMPLETE | `bjuice_v2_hg002_multi_au_config.py`; direct formula is `ROUND_DOWN(target / C_ILMN, 12)`. |
| FIX-002 | Preserve measured ONT end-hour retargeting without manually editing manifests. | COMPLETE | The plan still validates its seven cumulative ONT windows; its prior-coverage fields are audit metadata only. |
| FIX-003 | Preserve exact DYEC release eligibility for the literal command. | COMPLETE | New immutable `dyec_builds.18.0.7` snapshot, source/payload parity required. |
| FIX-004 | Validate, release, generate corrected manifests, dry-run, then launch a fresh root. | IN_PROGRESS | The failed root remains immutable; no FSx data deletion is in scope. |
