# Runtime-cache export terminal receipts

The cache workstream used only `dyec runtime-cache export` and stopped before any DRA or S3 object delivery.

| Attempt | Receipt SHA-256 | Terminal state | Key evidence |
|---|---|---|---|
| `pclu18045_runtime_cache_20260819t070050z` | `9b6ac429727b89fa2f9a6f6639f8a7e4b6d7b295a431f53372ba074268652ef6` | `error`, staging verification | SSM `354067bc-72fe-4868-8dbc-a2f7562b227b` returned `rc=1` when an allocation-sensitive byte-count check rejected a copied Conda environment.  No DRA/S3 task was created; staged FSx data was retained. |
| `pclu18045_runtime_cache_20260819t071328z` | `eb056a8d1549a3a65e8613b8ca765acc5a1fa2bbbc85ec87df8c92dc8df4e822` | `error`, staging timeout | SSM `38e08c9f-7b30-453d-806d-ac25cc397f7c` timed out with `rc=137` after 31/42 Conda entries, before either of two images and before the source-namespace completion marker.  No DRA/S3 task was created; staged FSx data was retained. |

Both attempted destinations remain empty dedicated prefixes below `s3://lsmc-ssf-sequencing-data/derived/runtime_cache_exports/pclu-18045/`.  Neither attempt deleted its source or staged FSx root.  The uncommitted cache-import/post-install implementation is explicitly excluded from DYEC `18.0.57` because there is no verified cache-export source to import.
