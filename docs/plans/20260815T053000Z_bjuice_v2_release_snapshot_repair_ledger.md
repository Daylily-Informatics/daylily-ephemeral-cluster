# Bjuice v2 release snapshot repair ledger

DYEC `18.0.5` contains the repaired DayOA `15.0.2` pin in `current` but lacks
a numeric eligibility snapshot, so `--dyec-version 18.0.5` fails closed before
any launch. This `18.0.6` release adds a deliberately scoped immutable snapshot
for the literal Bjuice v2 multi-AU command only; it does not claim unrelated
catalog commands are eligible.

Verification requires source/payload byte parity, successful exact-snapshot
catalog resolution, and a fresh dry controller before live launch.
