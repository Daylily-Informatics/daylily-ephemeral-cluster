# Bundle 1b Bjuice + Inflection catalog dry-run ledger

Created: 2026-08-21T03:33:09Z

Status: in progress — dry-run preparation and diagnosis only. No live workflow,
export, FSx cleanup, source-data mutation, tag, or release is authorized by this
ledger.

## Scope and terminal rule

Prepare one test-only command-catalog row for the supplied Bundle 1b full
analysis-unit manifest set. The only authorized remote execution is a DYEC
catalog render and dry controller using the exact catalog command with
`-j 456 -T 1 -p -k -n`. A passing dry controller must be `rc=0` with zero
submitted jobs. A live continuation, export, or deletion needs a subsequent
explicit authorization.

## Gate 0 inventory

| Item | Evidence |
| --- | --- |
| Private working directory | `/Users/jmajor/.codex-worktrees/dyec-bundle1b-bjuice-inflection-20260821` |
| Private branch | `codex/bundle1b-bjuice-inflection-dry-20260821` |
| Base commit | `581d770f2a3c96311ff5ebe748c9df4e76c7ddf8` |
| DYEC | `19.0.4` |
| Cluster | `pclu-18045`, `us-west-2`; healthy at Gate 0 |
| DayOA pin | `16.0.3`, commit `bcd2e804a063be33dbc0ae414b82b5fee061741a` |
| Manifest directory | `docs/jem/bjuice_validation/configs/bundle1b` |
| Runtime config | `bjuice_validation_bundle1b_hiomr2.yaml`, SHA-256 `276dd735b210a621ca65c84525f5a3bbc5d0114da7bbd78fc41096b19d18bb92` |
| Manifest rows | 28 specimens; 28 samples; 64 libraries; 64 sequencing inputs; 32 analysis units; 64 analysis-unit inputs |
| Source mounts | ILMN `/fsx/run_dir_mounts/20260629_LH01106_0014_B23WV5HLT4/`; ONT `/fsx/run_dir_mounts/pca100-2026/`; both verified readable before initial controller attempt |
| Truth contract | HG002 `TRUTH_DATA_DIR` is nonblank; runtime config sets HG002 Truvari SV VCF, TBI, and BED under `truvari_sv_benchmark.truthsets.HG002` |

## Catalog contract

Command ID: `inflection-bjuice-bundle1b-product-v0.9`

Targets:

1. `produce_sentdhiomr2_slim_kitchensink_mega`
2. `produce_sentdhiomr2_inflection_analytical_package`

The supplied runtime config is hash-bound into the staged controller payload and
is materialized only at `config/dyec_runtime_config.yaml` inside the pinned
DayOA clone. The target path is explicitly whitelisted as an analysis artifact;
no versioned DayOA source path is changed.

## Controller evidence

| Attempt | Analysis root | Result | Evidence / disposition |
| --- | --- | --- | --- |
| Initial shared-checkout dry controller | `/fsx/analysis_results/pclu-18045/pclu18045-bundle1b-bjuice-ifx-20260821t0343z/daylily-omics-analysis` | failed, controller/day-run `rc=2`; zero Slurm jobs submitted | Root retained. This predates the private branch and is diagnostic evidence only, not a passing dry proof. Use DYEC controller logs after the CLI observability correction; do not delete or continue it. |
| Private-branch render | `pclu18045-bundle1b-bjuice-ifx-20260821t0455z` | SUCCESS | Rendered with `--profile lsmc --region us-west-2 --cluster pclu-18045 --project pclu-18045 --cost-center pclu-18045-ccenter`, supplied Bundle 1b manifests, and corrected runtime YAML. The resolved command contains `-j 456 -T 1 -p -k -n` and `--configfile config/dyec_runtime_config.yaml`. |
| Private-branch dry controller | `/fsx/analysis_results/pclu-18045/pclu18045-bundle1b-bjuice-ifx-20260821t0455z/daylily-omics-analysis` | SUCCESS | Session `pclu18045-bundle1b-bjuice-ifx-20260821t0455z-dry`; attempt `e05ddf9e-0cd1-4a71-8fee-90b0757ddb4b`; controller, `dy-r`, and Snakemake `rc=0`; zero submitted and zero finished Slurm jobs. Exact Snakemake log: `.snakemake/log/2026-08-21T041543.852233.snakemake.log`. No live continuation, export, or cleanup occurred. |

### Failure diagnosis and correction

The preserved controller log reports `WorkflowError:
truvari_sv_benchmark.env_yaml must select immutable truvari_v0.2.yaml`.
The supplied YAML had `../envs/truari_v0.2.yaml`, while the immutable DayOA
`16.0.3` rule accepts the basename `truvari_v0.2.yaml`. The only correction is
the runtime-config spelling change to `../envs/truvari_v0.2.yaml`; it changes
the config SHA from `84e84e2ae5024b5211a291b2938f93d3bd9476bd3074618336089668f433c916`
to the Gate 0 SHA above. DayOA source remains unchanged.

## Safety boundary

- No raw Snakemake, SSH, SSM, AWS CLI, or headnode source modification.
- No runtime config is placed outside the DayOA clone.
- No export or cleanup occurs for failed or dry-only roots.
- Bundle 2, 3, and 4 require their own supplied six-manifest/runtime-config
  inputs and their own catalog rows; this Bundle 1b row does not discover or
  substitute them.
