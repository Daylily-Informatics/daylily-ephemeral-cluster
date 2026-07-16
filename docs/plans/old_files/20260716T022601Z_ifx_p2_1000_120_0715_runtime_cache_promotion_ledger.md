# IFX Persistent-2 Runtime Cache Promotion Ledger

Opened: 2026-07-16T02:26:01Z

## Objective

After the ten-sample DayOA 11.0.10 HIOMRS kitchensink controller began
submitting Slurm work, promote complete cache misses from cluster
`ifx-p2-1000-120-0715` into the canonical S3-backed cache used to seed and
link runtime environments on future clusters:

```text
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/conda/
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/containers/
```

## Guardrails

- Do not stop, requeue, modify, or otherwise administer Slurm jobs or the
  DayOA controller.
- Copy only real conda directories containing `conda-meta/history` and their
  matching YAML definitions.
- Do not dereference container symlinks that already point into the shared
  cache.
- Do not upload incomplete or temporary cache artifacts.
- Do not delete local or S3 artifacts.
- Existing S3 keys must not be overwritten. A nonempty candidate prefix or an
  existing YAML key is a hard collision and must stop that promotion.
- Any temporary S3 write permission is restricted to the exact missing conda
  hash prefixes/YAML keys and is removed after terminal verification.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Live workload gate | At 2026-07-16T02:22:37Z jobs 242 and 261-282 included running `fastqc_subsampled`/`seqfu` work plus pending 192-CPU HIOMRS preparation groups. |
| Headnode | `i-09b566e847c16233b`, host `ip-10-0-0-22`, cluster `ifx-p2-1000-120-0715`, region `us-west-2`. |
| FSx | `fs-0cc0657362d4140c2`, 12,000 GiB Persistent_2, 1,000 MB/s/TiB, mounted read/write at `/fsx`. |
| Complete local conda cache misses | 18 real directories under `/fsx/resources/environments/conda/ubuntu/ip-10-0-0-22`; every one contains `conda-meta/history` and a matching YAML. Allocated cache size was about 19 GiB. |
| Incomplete markers | None found beneath `/fsx/resources/environments`. |
| Container cache misses | None. All observed `.simg` entries are symlinks to three existing images under `/fsx/references/runtime_assets/cached_envs/containers/`. |
| S3 collision preflight | All 18 candidate conda prefixes were empty and all 18 matching YAML keys were absent. |
| Existing headnode permissions | Read/list only for `lsmc-dayoa-references-usw2`; no `s3:PutObject` permission. |

## Execution Ledger

| ID | Action | Status | Evidence / notes |
|---|---|---:|---|
| CACHE-001 | Inventory live queue and cache sources | SUCCESS | Slurm gate met; 18 complete conda cache misses, zero real container cache misses, and zero incomplete markers. |
| CACHE-002 | Validate destination and collision state | SUCCESS | Canonical boot-linked prefixes confirmed in DYEC source; every exact conda hash prefix/YAML key is absent in S3. |
| CACHE-003 | Install temporary least-privilege write policy | SUCCESS | Inline role policy `codex-runtime-cache-promotion-20260716T022601Z` is limited to 36 exact resources (18 hash prefixes plus 18 YAML keys) and expires automatically at 2026-07-17T02:30:00Z. |
| CACHE-004 | Promote complete conda environments | IN_PROGRESS | Tmux `runtime-cache-promote-20260716T022601Z` passed its repeated 18-prefix collision preflight and began the first environment at 2026-07-16T02:36:34Z. It runs at `nice 10`, `ionice` best-effort 7, four S3 transfer workers, and one environment at a time. |
| CACHE-005 | Verify S3 readback and future-cluster linkage contract | PENDING | Require zero dry-run differences, matching YAML sizes, and readable destination objects. |
| CACHE-006 | Remove temporary write policy | PENDING | Must occur after success or terminal failure; verify role returns to its baseline policy set. |

## Execution Notes

- 2026-07-16T02:34:36Z: The first helper attempt failed closed before its
  first upload (`rc=20`). The overly broad filename scan treated normal PCRE2
  documentation named `pcre2partial.html` and `pcre2partial.3` as construction
  markers. The completion contract remains the historical, evidence-backed
  `conda-meta/history` plus matching environment YAML check; the false-positive
  filename scan was removed. Destination collision readback remained empty.
- 2026-07-16T02:36:34Z: Corrected helper passed all 18 repeated destination
  collision checks and began environment
  `006efecfc3daf71d6e8891c8c5ec264e_`. A bounded S3 readback during transfer
  showed 12,446 objects / 1,596,549,135 bytes already present in that new hash
  prefix; the promoter remained `RUNNING`.

## Candidate Environment Hashes

```text
006efecfc3daf71d6e8891c8c5ec264e_
0305ee2e0cf74ce3b5ebed91f8dc94a5_
06953e3f381c391f984f782b21b9d543_
0980c3945506ecfe0a3eccf79bbab0f4_
1639057e83945a2943775982a7969933_
30e61a2dc39d32749b2851fe08f1743a_
38ded4f03b978d40a3ef9f7e9be498b4_
3923c3190c5cf1716e7831acf8ef0441_
519f82430c4bfa01b8224f13fd1aefb5_
59542afef44767b88a4ac894bfb19812_
6dbf8ec337fc9fc05441f68fb3af67ac_
94dcae0c033f0b59e9e0c3192024612f_
9c24da75d9c05fbc2e1c5c34d0ce0a62_
a4227e5a83b9623c5c90f45f821fd559_
bba811144d767ed3dd48f622d65d7594_
c62a55f9f4dec85e2c5a054c4d72a6f8_
c8d70b7965aeb5c50c5da862c810d183_
d08982b3a831bcf512944528e46e2c82_
```
