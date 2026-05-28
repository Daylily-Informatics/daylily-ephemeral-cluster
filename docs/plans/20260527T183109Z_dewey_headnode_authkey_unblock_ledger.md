# Dewey Headnode Authkey Unblock Ledger

Created: 2026-05-27T18:31:09Z

## Objective

Use the tested local `.tailscale_key` to unblock current and future DayEC headnodes reaching `https://dewey.day.lsmc.bio/`: store the key as the expected SSM SecureString, ensure new headnode instance roles receive permission to read it, update DYEC template rendering and packaged cluster YAMLs, test the changes, and publish runtime assets needed by newly created clusters.

No Tailscale key value may be printed or committed.

## Gate 0 Inventory

| Field | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/running-nextflow-pipes-doc...origin/codex/running-nextflow-pipes-doc` |
| Dirty state | Pre-existing modified ledgers/docs plus untracked run artifacts and `.tailscale_key`; do not revert unrelated work. |
| Key validation | Prior isolated Docker validation enrolled two Tailscale userspace nodes with `.tailscale_key`; both reached `https://dewey.day.lsmc.bio/` with `http_code=307`; test nodes logged out and removed. |
| SSM target | `/daylily/dayec/tailscale/headnode-authkey` in `us-west-2`, AWS profile/account `lsmc` / `108782052779`. |
| Initial SSM state | `aws ssm describe-parameters --region us-west-2 --parameter-filters Key=Name,Option=Equals,Values=/daylily/dayec/tailscale/headnode-authkey` returned `[]`. |
| Boot script contract | `config/day_cluster/post_install_ubuntu_combined.sh` reads that parameter via `aws ssm get-parameter --with-decryption`, runs `tailscale up --auth-key=... --accept-dns=false --accept-routes=false`, then curls Dewey. |
| Cluster YAML contract | Headnode policies are declared under `HeadNode.Iam.AdditionalIamPolicies` in `config/day_cluster/*.yaml` templates and packaged copies under `daylily_ec/resources/payload/config/day_cluster/`. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SSM-001 | AWS SSM | Store tested `.tailscale_key` as SecureString without printing it | SUCCESS | feature_implementation | Gate 5 | orchestrator | `boto3 ssm.put_parameter(Name="/daylily/dayec/tailscale/headnode-authkey", Type="SecureString", Overwrite=True)` with profile `lsmc`, region `us-west-2`; returned `Version=1`. `describe_parameters` now reports `Type=SecureString`. | Missing SecureString parameter prevented headnodes from reading the Tailscale authkey. | Key value was never printed and `.tailscale_key` remains untracked. |
| IAM-001 | AWS IAM | Ensure a managed policy grants headnodes `ssm:GetParameter` on the authkey parameter | SUCCESS | feature_implementation | Gate 5 | orchestrator | Created/verified `arn:aws:iam::108782052779:policy/dayec-headnode-tailscale-authkey-read`; default version `v1` allows only `ssm:GetParameter` on `arn:aws:ssm:us-west-2:108782052779:parameter/daylily/dayec/tailscale/headnode-authkey`. Attached to existing headnode roles `goodole3-RoleHeadNode-UruxdILy0RYK` and `pilot-xfer-RoleHeadNode-TLLRCMD5jHnB`. | Existing and future headnodes needed least-privilege SSM read permission for the authkey. | Existing headnode role attachment checks returned `attached=true` for both current headnodes. |
| CODE-001 | DYEC code | Add deterministic headnode Tailscale authkey policy support to IAM preflight and cluster template rendering | SUCCESS | feature_implementation | Gate 2 | orchestrator | Changed `daylily_ec/aws/iam.py`, `daylily_ec/aws/__init__.py`, `daylily_ec/workflow/create_cluster.py`, and `daylily_ec/render/renderer.py`. Render substitution now sets `REGSUB_HEADNODE_TAILSCALE_IAM_POLICY` to `arn:aws:iam::<account>:policy/dayec-headnode-tailscale-authkey-read`. IAM preflight now ensures that managed policy exists and is current. | Cluster rendering previously had no deterministic Tailscale authkey policy ARN for headnode templates. | Future `daylily-ec create` runs render the policy ARN without service-side discovery or fallback. |
| YAML-001 | Cluster templates | Add the headnode policy ARN substitution to all source and packaged headnode YAML definitions | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Added `- Policy: ${REGSUB_HEADNODE_TAILSCALE_IAM_POLICY}` under `HeadNode.Iam.AdditionalIamPolicies` in `config/day_cluster/prod_cluster.yaml`, `prod_cluster_dragen.yaml`, `prod_cluster_variant.yaml`, `cromwell_test.yaml`, `regions/all_clusters.yaml`, and the packaged copies under `daylily_ec/resources/payload/config/day_cluster/`. Render probe for `config/day_cluster/prod_cluster.yaml` produced the three expected headnode policies: `pcluster-omics-analysis`, `AmazonSSMManagedInstanceCore`, and `dayec-headnode-tailscale-authkey-read`. | Future headnodes must receive permission from the ParallelCluster headnode definition, not manual post-create attachment. | The shared boot script still gates Tailscale/Dewey work inside `if [ "${cfn_node_type}" == "HeadNode" ]; then`; compute nodes do not read the headnode authkey. |
| TEST-001 | Validation | Run focused tests and syntax checks for IAM, renderer, templates, and headnode init | SUCCESS | contract_test | Gate 5 | orchestrator | `source ./activate && python -m pytest tests/test_iam.py tests/test_renderer.py tests/test_packaged_defaults.py tests/test_headnode_init.py tests/test_workflow.py::TestClusterBootConfigPublish -q` -> `88 passed in 1.25s`. `bash -n` passed for both source and packaged `post_install_ubuntu_combined.sh`. Live SSM Dewey checks as `ubuntu`: `goodole3` command `be143ea4-35f9-448e-9178-bb1c11f0aa9d`, `TAILSCALE_IP=100.123.13.96`, `DEWEY_HTTP_CODE=401`, `DEWEY_RESOLVED_IP=100.75.231.53`; `pilot-xfer` command `f653a848-cd8d-4f47-b9c7-b95bcb57d108`, `TAILSCALE_IP=100.124.246.64`, `DEWEY_HTTP_CODE=401`, `DEWEY_RESOLVED_IP=100.75.231.53`. | Needed both unit/template coverage and live confirmation that current headnodes can use the key. | HTTP 401 is acceptable reachability evidence for Dewey because curl reached the service through the tailnet and received an HTTP response. |
| PUB-001 | Runtime assets | Publish updated cluster boot/config assets to the active S3 runtime-assets location for new clusters | SUCCESS | feature_implementation | Gate 5 | orchestrator | `publish_cluster_boot_config` uploaded `post_install_ubuntu_combined.sh`, `sbatch`, and `sleep_test.sh` to `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/`; S3 readback byte counts and SHA-256 matched packaged local assets for all three files. | New clusters fetch boot assets from active reference runtime assets. | Active S3 runtime assets match packaged repo assets. |

## Final Evidence

- SSM authkey parameter exists as `SecureString` at `/daylily/dayec/tailscale/headnode-authkey` in `us-west-2`.
- Managed policy exists at `arn:aws:iam::108782052779:policy/dayec-headnode-tailscale-authkey-read`.
- `config/day_cluster/prod_cluster.yaml` headnode definition now renders:
  - `arn:aws:iam::108782052779:policy/pcluster-omics-analysis`
  - `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore`
  - `arn:aws:iam::108782052779:policy/dayec-headnode-tailscale-authkey-read`
- Current headnodes `goodole3` and `pilot-xfer` can reach `https://dewey.day.lsmc.bio/` through Tailscale and receive HTTP `401`.
- All tracking rows are terminal `SUCCESS`.
