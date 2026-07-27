## Control Ledger

Controlling request: release the merged ONT SeqQC scheduler correction, advance DYEC to that DayOA release, then advance DYEC's self-pin in a second tagged release.

| ID | Repository | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| REL-01 | DayOA | Tag merged main as `13.0.59`. | SUCCESS | Annotated tag `13.0.59` points to `c148f3c7b9fdea0cb813b8c08b5d9bfeb623eaab`. | Pushed to origin. |
| REL-02 | DYEC | Update both command-catalog copies to DayOA `13.0.59`; release as `15.0.11`. | SUCCESS | Annotated tag `15.0.11` points to `605e1b922ef4256e7b1c7e614fdb93a27d9a8989`; 295 focused tests passed. | Includes the ONT composite SeqQC command. |
| REL-03 | DYEC | Advance DYEC's self-pin to `15.0.11`; release as `15.0.12`. | IN_PROGRESS | Source and packaged global configuration now carry the `15.0.11` self-pin. | Must be a separate commit and annotated tag. |
