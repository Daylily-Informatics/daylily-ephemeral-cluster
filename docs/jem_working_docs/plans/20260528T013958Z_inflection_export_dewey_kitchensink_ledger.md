# Inflection HG003 Hybrid Calls Export And Dewey Kitchen Sink Ledger

## Gate 0

Created: 2026-05-28T01:39:58Z

Scope:
- Create `/fsx/analysis_results/ubuntu/for_inflection/hg003_hybrid_calls.tgz` from the active `goodole3` headnode by archiving only:
  - `results/day/hg38_broad/reports`
  - `results/day/hg38_broad/other_reports`
  - `results/day/hg38_broad/20260514-LH01106-0009-B23TVLGLT4-INFLECTION-HIOMR-ILMN20X-ONT10X-HG003-a-inflection-HIOMR-ILMN20x-ONT10x-0-HG003-a-PF-ILMN-NOVASEQ`
- Export `/fsx/analysis_results/ubuntu/for_inflection` to S3 using the cluster-named derived-data pattern:
  - `s3://lsmc-ssf-sequencing-data/derived/goodole3/analysis_results/ubuntu/for_inflection/`
- Verify the S3 export before considering FSx cleanup.
- Generate a direct S3 presigned URL for the exported `hg003_hybrid_calls.tgz`.
- Restart the `ILMN20x-ONT10x` Snakemake workflow using the same units table and run the hybrid kitchen-sink and Dewey registration rules.

Safety boundary:
- Deleting `/fsx/analysis_results/ubuntu/for_inflection` is destructive. It is not approved by this first request alone. The cleanup row remains `BLOCKED` until the user gives a separate explicit confirmation after export verification.
- Existing unrelated local worktree changes are not owned by this ledger and must not be reverted.

Environment and evidence:
- DAY-EC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Local branch/status at Gate 0: `codex/running-nextflow-pipes-doc...origin/codex/running-nextflow-pipes-doc`, with pre-existing modified/untracked plan artifacts, `AGENTS.md`, `.network-overlay_key`, and unrelated local VCF/presign files.
- Cluster/profile/region: `goodole3`, `lsmc`, `us-west-2`.
- Headnode shell: interactive SSM shell as `ubuntu`, `/bin/bash`.
- Run dir: `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`.
- Genome code: `hg38_broad`.
- Source sample tree is the unique `ILMN20X-ONT10X` directory under `results/day/hg38_broad`.
- Source payload size before compression: reports `306K`, other_reports `33K`, 20x10 sample tree `122G`.
- `/fsx` capacity before archive: `4.4T` size, `763G` used, `3.7T` available, `18%` used.
- Active non-target controller state before this ledger: `ILMN15x-ONT7x` controller and Slurm jobs were stopped; no Slurm jobs remained for `ubuntu`.

## Rows

| ID | Requirement | Status | Category | Approval Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|
| G0-001 | Record source paths, destination pattern, shell identity, dirty-state boundary, and destructive-delete gate. | SUCCESS | plan_amendment | Gate 0 | This Gate 0 section. |  | Initial operating boundary recorded. |
| TAR-001 | Create `/fsx/analysis_results/ubuntu/for_inflection/hg003_hybrid_calls.tgz` with only reports, other_reports, and the 20x10 sample directory. | SUCCESS | feature_implementation | Gate 1 | Headnode `tar -I "pigz -p 16"` completed with `TAR_RC=0`; archive size `122G`. |  | Archive created at `/fsx/analysis_results/ubuntu/for_inflection/hg003_hybrid_calls.tgz`. |
| EXP-001 | DRA-export `/fsx/analysis_results/ubuntu/for_inflection` to the cluster-named S3 derived-data prefix. | SUCCESS | feature_implementation | Gate 1 | `dyec export --cluster-name goodole3 ...` receipt `docs/plans/20260528T013958Z_inflection_export_dewey_kitchensink/export/fsx_export.yaml`: `status: success`, task `task-0157823fa7e0932d2`, DRA `dra-0c08efdb5b290d23f`, `detach_lifecycle: DELETED`. |  | Export completed to `s3://lsmc-ssf-sequencing-data/derived/goodole3/analysis_results/ubuntu/for_inflection/`. |
| VER-001 | Verify exported S3 object inventory, including the new `.tgz`. | SUCCESS | contract_test | Gate 1 | `aws s3api head-object` on `derived/goodole3/analysis_results/ubuntu/for_inflection/hg003_hybrid_calls.tgz` returned `ContentLength=130446731789`, `ETag="9e1fda08448a26f723513ddb0ea82a0d-3111"`, `LastModified=Thu, 28 May 2026 01:50:54 GMT`. |  | S3 object verified. |
| DEL-001 | Delete `/fsx/analysis_results/ubuntu/for_inflection` only after successful export and separate explicit user confirmation. | SUCCESS | legitimate_safety_handling | Gate 2 | User approved deletion after S3 confirmation; S3 object confirmed; headnode cleanup command `2f31fb8f-54ff-4021-ac48-d53753df39f1` ran as `ubuntu`, showed `BEFORE=122G`, only entry `hg003_hybrid_calls.tgz`, and reported `FOR_INFLECTION_REMOVED`. |  | FSx staging directory removed after export verification. |
| URL-001 | Generate a direct S3 presigned URL for the exported `.tgz`, expiring in 7 days. | SUCCESS | feature_implementation | Gate 3 | `aws s3 presign ... --expires-in 604800` completed; URL expiration computed as `2026-06-04T01:55:28+00:00`. |  | Direct S3 presigned URL generated and reported. |
| DEWEY-001 | Register exported `.tgz` with live Dewey. | SUCCESS | feature_implementation | Gate 3 | Initial local token attempts reached live Dewey but returned `401 Invalid bearer token`; live `aws3041` inspection command `8af93d34-f1b8-478d-a309-ff926cd6828f` confirmed current `dewey-lsmcok1` config on host as `ubuntu`; registration command `55adb375-69fa-457e-b6ec-8d3d5cf066c1` returned artifact `M-DGX-9S5Q`; read-back command `18a1e12f-a268-45dd-b7b6-665c6c7d6ea7` returned HTTP 200 for `s3://lsmc-ssf-sequencing-data/derived/goodole3/analysis_results/ubuntu/for_inflection/hg003_hybrid_calls.tgz`; evidence file `docs/plans/20260528T013958Z_inflection_export_dewey_kitchensink/dewey_hg003_hybrid_calls_registration_response.json`. |  | Live Dewey artifact registration complete as `M-DGX-9S5Q`. |
| RUN-001 | Restart 20x10 Snakemake with the kitchen-sink and Dewey registration rules using `config/units.ILMN20x-ONT10x.tsv`. | BLOCKED | feature_implementation | Gate 4 | Readiness command `fc84644f-6aa2-4886-8567-d98b6e32ef94` showed `goodole3` resolves `dewey.day.lsmc.bio` to `52.89.110.76` and times out unless forced to `100.75.231.53`; config scan showed no active `qeo_registration` block; metadata scan `44f018e5-d8a8-4af7-9995-be43adffac9e` found no `analysis_euid`, `run_euid`, or `workset_euid` in the run config, only the `RUNID` and experiment IDs in `config/units.ILMN20x-ONT10x.tsv`. | Required explicit QEO identity/config and overlay-network DNS path are missing for this run. | Not launched; starting the registration targets now would fail or require inventing identities/secrets. |

## Updates

- 2026-05-28: User approved deletion of `/fsx/analysis_results/ubuntu/for_inflection` after `.tgz` confirmation on S3.
- 2026-05-28: User amended Dewey requirement: skip Dewey registration and generate a direct 7-day S3 presigned URL instead.
- 2026-05-28: User resumed and requested trying Dewey registration; the exported `.tgz` was registered directly with live Dewey as artifact `M-DGX-9S5Q`.
- 2026-05-28: The 20x10 kitchen-sink/QEO controller was not restarted because the run lacks explicit `qeo_registration` identities and `goodole3` is not receiving overlay-network split DNS for `day.lsmc.bio`.
- 2026-05-28: Read-only network debug showed `goodole3` has general outbound internet: Google returned HTTP 204, AWS returned HTTP 200, S3 and STS endpoints returned redirects, and `aws sts get-caller-identity` succeeded. The Dewey failure is narrower: `network-overlay dns status` reports network overlay DNS disabled even though split-DNS route `day.lsmc.bio -> 100.75.231.53` is advertised; public `dewey.day.lsmc.bio` resolves to `52.89.110.76`, but the Dayhoff public service SG only allows TCP 443 from `152.44.152.3/32` and `108.212.69.87/32`, while `goodole3` egresses as `44.242.81.64`.
