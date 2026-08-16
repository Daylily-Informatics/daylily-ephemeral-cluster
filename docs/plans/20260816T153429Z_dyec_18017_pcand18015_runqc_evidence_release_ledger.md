# DYEC 18.0.17 pcand-18015 three-platform RunQC evidence release ledger

Created: 2026-08-16T15:34:29Z  
Controlling request: Run the current Illumina, ONT, and Ultima sequencing-QC catalog commands on `pcand-18015`, export successful results without deleting FSx data, and record the verified S3 evidence in the current DYEC catalog. Ursa is explicitly out of scope.

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| EVD-001 | Record exact DayOA `15.0.9` Illumina RunQC proof. | SUCCESS | Controller `pcand18015_ilmn_runqc_1509_live2_20260816T1404Z` exited `rc=0`; export task `task-0bcbd1dad1a9a53a2` succeeded; DRA `dra-032a2da68b14f742d` detached; FSx was preserved; the S3 MultiQC report is 4,039,466 bytes. |
| EVD-002 | Record exact DayOA `15.0.9` ONT RunQC proof. | SUCCESS | Controller `pcand18015_ont_runqc_1509_live_20260816T1422Z` completed all 10 steps and exited `rc=0`; export task `task-061399116a85f689b` succeeded; DRA `dra-0186810753e344290` detached; FSx was preserved; native and demultiplexed S3 MultiQC reports are 2,845,229 and 3,406,609 bytes. |
| EVD-003 | Record exact DayOA `15.0.9` Ultima RunQC proof. | SUCCESS | Controller `pcand18015_ultima_runqc_1509_live_20260816T1513Z` exited `rc=0`; export task `task-0ab47c24639346b61` succeeded; DRA `dra-049aa949551c8d1be` detached; FSx was preserved; the S3 native MultiQC report is 3,645,480 bytes. |
| CAT-001 | Advance the three current catalog rows from pending `15.0.1` evidence to verified `15.0.9` evidence and retain exact S3 prefixes. | SUCCESS | Source and packaged catalog copies contain the same three successful validation rows and exact `validation_evidence_s3_uri_prefix` values. Historical numeric snapshots are unchanged. |
| VER-001 | Advance active operator-facing release references from DYEC `18.0.16` to `18.0.17`. | SUCCESS | Active docs and their release-contract expectation were changed mechanically; DayOA pins remain `15.0.9`. |
| REL-001 | Commit, merge, annotated-tag, publish GitHub Release, and build DYEC `18.0.17`. | OPEN | Pending release workflow. |

No test suite is rerun per the controlling user instruction. Release verification is limited to catalog parsing/show output, source/package catalog byte identity, `git diff --check`, exact tag provenance, and artifact metadata.

