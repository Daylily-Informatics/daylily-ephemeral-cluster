# DYEC 19.0.11 forced-reset ordering repair ledger

## Objective

Complete the public-DYEC repair of `pclu-18045` forced headnode configuration
after `19.0.10` removed the remote AWS identity dependency but exposed a
remaining pre-reset Git credential-helper dependency.

## Gate 0 — recorded 2026-08-21

| Item | Evidence |
| --- | --- |
| Starting release | Annotated `19.0.10`, commit `40f921afefe062befaed529228cc80bba592fdcf` |
| Release branch | `codex/release-19.0.11-force-reset-ordering` |
| Local controller | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Target | `pclu-18045`, `lsmc`, `us-west-2` |
| Credential authority | `/Users/jmajor/.config/daylily/state_pclu-18045_20260818151928.json` |
| 19.0.10 configure receipt | SSM `62e46ae5-6b01-455e-9d3b-f3969bb4cc4e`, rc `126` |
| Confirmed progress | The local cache-namespace resolution passed; the failure moved to the subsequent repository clone. |
| Remaining failure root cause | The forced Conda reset was ordered after the clone. The remote login shell auto-activated broken `DAY-EC`; the Git credential helper therefore invoked the missing `DAY-EC` Python interpreter before reset. |

## Change contract

- In `--force` mode, execute the named DAYOA/DAY-EC environment removal and
  Conda-cache cleanup before every repository clone, cache setup, or bootstrap
  operation.
- Retain local immutable stack resolution from `19.0.10` and all explicit
  credential/state authority requirements.
- Do not use any direct remote repair, raw AWS/SSM transport, or DayOA
  workflow execution.

## Verification and publish status

| Gate | Status | Evidence |
| --- | --- | --- |
| Source repair | complete | Forced reset is now the first mutable bootstrap step. |
| Pytest / git tests | intentionally not run | User explicitly requested no pytest or git tests. |
| Functional source commit | complete | `987bfb2be11deec891bfd00edba5e5a1e2f1385f` (`Run forced headnode reset before bootstrap`). |
| Release evidence commit, branch, and annotated tag | pending | This ledger finalization will be the annotated release commit. |
| Serialized forced configuration | pending | One public `dyec headnode configure --state-file … --force` attempt only. |

## Terminal record

Pending release publication and one serialized public-CLI configuration attempt.
