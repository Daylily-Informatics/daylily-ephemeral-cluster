# AlmaLinux ParallelCluster Contribution And Private Native DRAGEN Ledger

Created: `2026-07-10T02:52:21Z`

Controlling request: implement first-class AlmaLinux 8 custom-AMI support in
AWS ParallelCluster and its cookbook as public `iamh2o` contributions, while
keeping all private vendor-image, credential, workflow, and sample details in
the private LSMC repositories. Use the private extension to qualify native
DRAGEN and run the requested samples serially.

Ledger path:
`docs/plans/20260710T025221Z_almalinux_pcluster_native_dragen_ledger.md`

## Public Contribution Boundary

Public issues, branches, commits, tests, logs, and pull requests may contain
only generic AlmaLinux 8 custom-AMI material. They must not contain vendor or
workload names, private/Marketplace AMI identifiers, LSMC account or resource
identifiers, credentials or license metadata, biological sample identifiers,
sequencing paths, references, or private validation outputs.

## Gate 0 Baseline

| Surface | Evidence |
|---|---|
| GitHub identity | `gh auth status`: active account `iamh2o`; git author `John Major <iamh2o@gmail.com>`. |
| ParallelCluster fork | `/Users/jmajor/projects/aws-parallelcluster`; `origin=iamh2o/aws-parallelcluster`; branch `codex/almalinux8-support` at upstream `develop` `3fd18745eb006138cfc7f6943beb2daf0db400dc`; clean. Existing fork was behind before the branch was created directly from upstream. |
| Cookbook fork | Created `iamh2o/aws-parallelcluster-cookbook`; checkout `/Users/jmajor/projects/aws-parallelcluster-cookbook`; branch `codex/almalinux8-support` at upstream `develop` `56a59988aac3a9889663810ecadbc16f02ff2156`; clean. |
| Contribution contract | Both upstream repositories require significant features to start with an issue, target `develop`, include tests, and use focused changes. |
| Public test source | Official AlmaLinux Foundation AlmaLinux 8 AWS images and mocked AlmaLinux OS fixtures only. |
| EFA boundary | User confirmed that EFA may be omitted from the workload-specific cluster. Public CLI validation now rejects EFA-enabled AlmaLinux 8 configs and the cookbook explicitly skips EFA installation because the current EFA installer rejects AlmaLinux 8. Private cluster configs keep EFA disabled. |
| DYEC | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`; `jem-dev`; HEAD `0f845eef2c575759752f7edb61af02583d272ff6`; pre-existing dirty command-catalog log and untracked summary JSON must be preserved. Active dependency pin is `aws-parallelcluster==3.15.0`. |
| DayOA | `/Users/jmajor/projects/lsmc/daylily-omics-analysis`; `jem-dev`; HEAD `d81108d7f59bd2f4c31aa5045afbdce5d40977d5`; pre-existing contamination-rule/config/test edits must be preserved. The three profile `rule_config.yaml` files are already dirty and overlap only at file level with the requested DRAGEN section. |
| Credential boundary | Local credential file exists mode `600`, size `78`; private Secrets Manager value exists and matches byte-for-byte. Contents and hashes are prohibited from logs and public artifacts. Existing resource policy principals belong to the deleted cluster and are not reusable. |
| Known-good private runtime | Native full analyses previously completed only on the private vendor parent in `us-west-2b`; PCluster-derived RHEL migration failed FPGA partial reconfiguration. Private details stay outside public forks. |
| Live approval | User approved forks, public issues/branches/commits/pushes/draft PRs, non-destructive image/cluster/FSx/Spot/S3 work under the existing `$250` cost center, and private workflow execution. No destructive cleanup, force-push, upstream merge, or Slurm administration is approved. |
| Public AlmaLinux AMI | `us-west-2` `ami-0546451fe895ddabd`, owner `764336703387`, name `AlmaLinux OS 8.10.20260518 x86_64`, `Public=true`, `State=available`; this identifier is allowed only in generic public integration evidence. |
| Private AWS baseline | No pending/running/stopped `f2.6xlarge` instance is present; no cluster named `dragain10` is present. Current `us-west-2b` Linux/UNIX `f2.6xlarge` Spot price is `$0.6708/hr`; the configured 20% cap is `$0.80496/hr`. |
| Cost center | `dragen-followup-20260708` is `active`, monthly cap `$250`, allowed users `ubuntu` and `ec2-user`. |

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0-001 | Orchestration | Freeze repo, identity, credential, live-action, and public/private boundary evidence. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 table above. |  | Baseline recorded before implementation or public issue creation. |
| PUB-ISSUE-001 | GitHub | Open linked generic AlmaLinux 8 feature issues in both upstream repositories. | SUCCESS | feature_implementation | Gate 1 | Agent 5 | Opened `aws/aws-parallelcluster#7482`; `aws/aws-parallelcluster-cookbook` has GitHub Issues disabled, so the main issue records that the companion draft PR will carry the cookbook link. Public text contains only generic AlmaLinux custom-AMI material. |  | Available upstream issue surface is established before implementation. |
| PC-CLI-001 | aws-parallelcluster | Add first-class `almalinux8` custom-AMI schema, validators, ImageBuilder detection, metadata, docs, and tests on upstream `develop`. | SUCCESS | feature_implementation | Gate 1 | Agent 1 | Commits `26b6f581c` and `ae85dc3db` on `codex/almalinux8-support`; independently verified 575 schema/validator/core tests plus 180 configure/ImageBuilder tests, all passing. A further 326 validator/AlmaLinux focused tests passed after EFA was marked unsupported for AlmaLinux x86_64 and arm64 while EFA-disabled configs remain valid. Exact committed-range audit passed before each push. |  | Generic implementation pushed to `iamh2o/aws-parallelcluster`. |
| PC-CB-001 | cookbook | Add AlmaLinux 8 image/head/compute platform, package, service, Slurm, Lustre, explicit EFA omission, and tests on upstream `develop`. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | Commits `979ac2f0` and `5ba71747` on `codex/almalinux8-support`; 19 CloudWatch Python tests, 701 environment ChefSpec examples, 1,200 platform examples, 58 shared examples, and 16 Slurm examples passed with zero failures. The AlmaLinux EFA skip has two passing focused examples. All 66 changed Ruby files plus the three EFA files passed pinned Cookstyle `7.25.9`. Exact committed-range audit passed before each push. |  | Generic implementation pushed to `iamh2o/aws-parallelcluster-cookbook`. |
| PC-BACKPORT-001 | public forks | Maintain generic `v3.15.0` backport branches without private identifiers. | SUCCESS | feature_implementation | Gate 2 | Agents 1-2 | CLI commit `fb900dd94` and cookbook commit `16a84e46` are pushed on coordinated `codex/almalinux8-support-v3.15.0` branches. CLI broad coverage passed 790 tests before the EFA addition and 348 focused tests afterward. Cookbook AlmaLinux coverage passed CloudWatch, environment, platform, shared, entrypoint, and Slurm suites; 65 changed Ruby files passed pinned Cookstyle `7.25.9`. Both exact `v3.15.0..HEAD` ranges passed the leak audit before publication. | develop-only code and snapshots required version-specific resolution. | Backports are immutable build inputs; no private identifiers are present. |
| DYEC-001 | DYEC | Consume pinned operational forks and add explicit `dragen` cluster type with a qualified private child AMI. | IN_PROGRESS | feature_implementation | Gate 2 | Agent 3 | Added strict `dyec.parallelcluster_backport.v1` manifest validation, manifest-pinned executable routing, canonical private cluster template, and fail-closed qualified-image checks. Operational manifest remains intentionally absent until backport commits, cookbook checksum, and AMI qualification exist. | Required immutable build inputs do not exist yet. | Code complete; live integration pending. |
| DYEC-SPOT-001 | DYEC | Render one Spot `f2.6xlarge`, `MinCount: 0`, `MaxCount: 1`, single-instance partition cap plus 20%, and no fallback. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 3 | Private template renders one `dragen` Spot queue with one `f2.6xlarge`, `MinCount: 0`, `MaxCount: 1`; low-diversity F2 pricing uses Linux/UNIX Spot plus 20% subject to the global cap. Focused DYEC contract tests passed. |  | Implementation complete; live price/render proof remains under cluster validation. |
| DYEC-LIC-001 | DYEC/AWS | Create stable private secret and grant only new head/compute roles; hydrate mode-600 runtime file without logging contents. | IN_PROGRESS | legitimate_safety_handling | Gate 3 | Agent 3 | Created `dayec/dragen/lic_creds`; byte-equality check against the local mode-600 file returned `stable_secret_match=yes` without printing contents or hashes. Created managed policy `dayec-dragen-license-read` with exactly `secretsmanager:DescribeSecret` and `secretsmanager:GetSecretValue` on that secret. Live metadata-only preflight returned `PASS`, `secret_value_read=False`. The canonical template attaches this policy only to the new head/compute roles. | New cluster roles do not exist until cluster creation. | Secret and policy are ready; role attachment and runtime mode-600 hydration remain to be proved on the created cluster. |
| DAYOA-SNV-001 | DayOA | Replace only the fake DRAGEN-coded Sentieon rule with native SNV/map-align execution while preserving public aliases and outputs. | SUCCESS | feature_implementation | Gate 2 | Agent 4 | Replaced `dragen_aln_sort_snv` with native `/opt/edico/bin/dragen` map-align, BAM, SNV, and gVCF execution while preserving the genuine `sent_aln_sort_snv` rule and canonical DRGPG output path. Six focused native-workflow tests passed. |  | Implementation complete; live validation remains under NATIVE-SMOKE and HG002 rows. |
| DAYOA-ALL-001 | DayOA | Add native all-caller target with explicit SMN and direct multi-lane FASTQ-list input. | SUCCESS | feature_implementation | Gate 2 | Agent 4 | Added strict ordered lane-pair FASTQ-list generation, native all-caller rule, explicit `--enable-smn true`, output-family validation, and extracted SMN evidence. Six focused tests and script compilation passed. |  | Implementation complete; output naming and targeted JSON contract require live validation. |
| PUBLIC-LEAK-001 | public forks | Scan diffs, history, issues, PR text, logs, and artifacts for prohibited private terms before every publication. | IN_PROGRESS | contract_test | Gate 4 | Agent 5 | Fail-closed scanner has 19 passing tests and Ruff success. Both `develop` ranges, both `v3.15.0` ranges, issue text, planned commit messages, and revised PR bodies passed immediately before every commit, push, and PR edit. Known generic fixture exceptions are limited to two mock AMIs, the all-zero account fixture, and the official AlmaLinux Foundation owner account. Future public writes remain gated. |  |  |
| PUBLIC-AMI-001 | AWS/public | Build and boot a PCluster image from an official public AlmaLinux 8 AMI as generic integration proof. | IN_PROGRESS | contract_test | Gate 5 | Agent 5 | First develop build failed because the EFA installer returned `Unsupported operating system`; this produced the explicit EFA omission above. Corrected cookbook archive SHA-256 `17dcf43dda68595a4ddd18557fb81bf8a4afc794923b4d8c15877dc0501f21d1` is stored with exact CLI/cookbook commit metadata. Dry-run passed and image `almalinux8-pc316-develop-efa1-20260710` entered `BUILD_IN_PROGRESS`. | Current EFA installer does not support AlmaLinux 8. | Awaiting corrected image build and boot proof. |
| PRIVATE-AMI-001 | AWS/private | Build and qualify the private operational child while preserving kernel, driver, service, and FPGA behavior. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| CLUSTER-001 | AWS/private | Create `dragain10` in `us-west-2b`, mount ILMN-only inputs, and verify `/fsx` references. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| NATIVE-SMOKE-001 | AWS/private | Run native license/FPGA probe and stop on entitlement or PR failure. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| HG002-001 | DayOA/private | Run HG002 native validation with explicit SMN and require exit 0 plus SMN output. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| RELEASE-001 | DayOA/DYEC | Commit, test, push `jem-dev`, cut annotated non-v tags, and update DYEC pins in dependency order. | SUCCESS | feature_implementation | Gate 5 | orchestrator | A concurrent private release train committed and pushed DayOA `10.0.78`, then corrective `10.0.79`; DYEC `10.0.134` pins DayOA `10.0.79`, and DYEC self-pin tag `10.0.135` points configuration at release `10.0.134`. Current focused revalidation passed 23 DayOA native/Slurm tests and 37 DYEC backport/leak/F2/workflow tests. |  | Releases exist before live image qualification; any required live-validation fix must use the next patch versions rather than moving tags. |
| RUN-HG003-001 | DayOA/private | Run HG003 native SNV plus concordance serially through `dy-r -j 1`. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| RUN-NA20775-001 | DayOA/private | Run NA20775 native all-callers with explicit SMN serially. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| RUN-NA23687-001 | DayOA/private | Run NA23687 native all-callers with explicit SMN serially. | OPEN | live_validation | Gate 5 | Agent 5 | Pending. |  |  |
| PUB-PR-001 | GitHub | Push clean public branches and open linked draft PRs to upstream `develop`. | SUCCESS | feature_implementation | Gate 5 | Agent 5 | Pushed both `codex/almalinux8-support` branches and coordinated generic `codex/almalinux8-support-v3.15.0` backports. Opened linked drafts `aws/aws-parallelcluster#7483` and `aws/aws-parallelcluster-cookbook#3222`; each links issue `#7482` and the companion PR. Revised bodies explicitly document the generic EFA limitation. Exact range plus issue/PR text audits passed before every public write. |  | No merge, force-push, deletion, or release was performed. |
| FINAL-001 | Orchestration | Terminalize all rows and report objective completion separately from ledger completion. | OPEN | plan_amendment | Gate 5 | orchestrator | Pending. |  |  |

## Failure Contracts

- Any prohibited private identifier in a public diff, commit, issue, PR, log, or
  artifact blocks publication before it occurs.
- Missing public AlmaLinux source identity, missing private image identity,
  malformed manifests, missing reference markers, missing credential file,
  cost-center rejection, license rejection, FPGA PR failure, or unsupported
  imported output fails hard without fallback.
- DayOA execution uses `dy-r` only in a persistent interactive `ubuntu` tmux
  login shell with an explicit DayOA ref and analysis-root lock.
- No cluster, FSx, mount, secret, AMI, snapshot, S3 object, GitHub branch, or
  fork deletion is performed without separate destructive-action approval.
