# Legacy Code To Remove

Survey date: 2026-04-13

## Summary

The main supported operator path is much cleaner than the surrounding helper surface:

- `daylily-ec preflight/create/export/delete`
- `bin/daylily-ssh-into-headnode` using Session Manager
- laptop-side staging through `bin/daylily-stage-samples-from-local-to-headnode`
- headnode workflow launch through `bin/daylily-run-omics-analysis-headnode`

The remaining legacy debt is concentrated in shipped helper scripts, repo-checkout assumptions, and compatibility fallbacks that sit adjacent to the supported path. The highest priority items are the ones that still ship PEM-era guidance or still permit interactive / implicit fallback behavior in automation-facing helpers.

## Priority Findings

### 1. Active PEM-era guidance still ships in a non-quarantined script

Evidence:

- `bin/init_cloudstackformation.sh:3-4`
- `daylily_ec/resources/payload/bin/init_cloudstackformation.sh:3-4`

Why this is legacy:

- The script explicitly tells the operator to create an AWS key pair and keep a local `.pem` file.
- That directly contradicts the supported SSM-only contract.
- The payload copy means the stale guidance is still shippable, not just historical.

Recommended action:

- Remove or quarantine both copies.
- If the CloudFormation bootstrap is still needed, rewrite it to describe only the current supported auth model.

### 2. The SSH/PEM policy test has a real blind spot

Evidence:

- `tests/test_supported_no_pem_refs.py:32-44`
- `tests/test_supported_no_pem_refs.py:97-102`
- `bin/init_cloudstackformation.sh:4`

Why this matters:

- The supported-surface policy test scans `bin/` and `daylily_ec/resources/payload/bin/`.
- It bans `--pem`, `ssh -i`, `ssh_key_name`, and similar patterns, but it does not ban bare `.pem` references or generic “create a key pair” text.
- Today, `tests/test_supported_no_pem_refs.py` still passes even though `init_cloudstackformation.sh` contains explicit `.pem` guidance.

Recommended action:

- Extend the banned-pattern list to catch bare `.pem` references and PEM-era key-pair guidance.
- Keep the test broad enough that future text regressions fail without requiring exact command spelling.

### 3. A shipped delete helper still keeps interactive and repo-checkout fallbacks

Evidence:

- `daylily_ec/resources/payload/bin/daylily-delete-ephemeral-cluster:7-24`
- `daylily_ec/resources/payload/bin/daylily-delete-ephemeral-cluster:35-49`
- `daylily_ec/resources/payload/bin/daylily-delete-ephemeral-cluster:68-75`

Why this is legacy:

- The payload script still has a “dev fallback: repo checkout” path for resolving resources.
- It also advertises and implements interactive prompts when flags are omitted.
- That is the opposite of the current hard-fail / automation-first direction.

Recommended action:

- Stop shipping this legacy payload helper, or reduce it to a thin non-interactive wrapper around `daylily-ec delete`.
- Require explicit `--region`, `--cluster-name`, and `--profile` instead of prompting.

### 4. Headnode bootstrap still depends on a fixed repo checkout path

Evidence:

- `bin/install-daylily-headnode-tools:48-79`
- `bin/install-daylily-headnode-tools:141-178`
- `daylily_ec/resources/payload/bin/install-daylily-headnode-tools:48-79`
- `daylily_ec/resources/payload/bin/install-daylily-headnode-tools:141-178`

Why this is legacy:

- The managed login bootstrap hardcodes `repo_root="$HOME/projects/daylily-ephemeral-cluster"`.
- It sources `activate` from that checkout on every shell bootstrap path.
- It mutates `etc/analysis_samples_template.tsv` in place based on the cluster config.

Why this is risky:

- It couples headnode correctness to a checkout location instead of a package-owned install contract.
- It keeps repo-centric assumptions alive even after the env cleanup and packaging work.
- In-place mutation of a shared template is hard to reason about and can drift across runs.

Recommended action:

- Replace the fixed checkout assumption with a package/resources-dir based contract.
- Generate runtime-specific staging templates into a run-local path instead of mutating `etc/analysis_samples_template.tsv`.

### 5. Compatibility wrappers are still shipped as active entry points

Evidence:

- `bin/pcluster-ssm-to-headnode.bash:1-19`
- `bin/helpers/login_to_cluster.sh:1-7`
- `daylily_ec/resources/payload/bin/helpers/login_to_cluster.sh:1-7`

Why this is legacy:

- These scripts do not add behavior; they only preserve older command names or access patterns.
- They keep extra supported-looking surfaces alive instead of forcing the single supported entry point.

Recommended action:

- Remove or quarantine these wrappers.
- Keep `bin/daylily-ssh-into-headnode` as the single documented connect command unless there is a concrete compatibility requirement to preserve them.

### 6. A retired staging script still lives in the active `bin/` tree

Evidence:

- `bin/daylily-stage-analysis-samples-local-experimental:4-16`
- `daylily_ec/resources/payload/bin/daylily-stage-analysis-samples-local-experimental` (same content and status)

Why this is legacy:

- The script already declares itself retired and exits with an error.
- Even so, it remains in the active shipped tree rather than in quarantine/archive.
- It still teaches a repo-checkout on-headnode workflow (`cd ~/projects/daylily-ephemeral-cluster`).

Recommended action:

- Move it to quarantine/archive and keep only the supported staging helpers in active `bin/`.

### 7. Helper scripts still auto-bootstrap instead of hard-failing

Evidence:

- `daylily_ec/resources/payload/bin/helpers/ensure_dayec.sh:29-53`
- `daylily_ec/resources/payload/bin/helpers/watch_cluster_status.py:58-67`

Why this is legacy:

- `ensure_dayec.sh` silently tries `source ./activate` based on a repo-relative path.
- `watch_cluster_status.py` still has a “legacy behaviour” fallback that reads the first cluster in the region when no cluster name is provided.

Why this matters:

- Both patterns preserve implicit behavior instead of requiring explicit operator intent.
- They make failures less precise and increase the chance of acting on the wrong environment or wrong cluster.

Recommended action:

- Make environment activation explicit and fail if `DAY-EC` is not already available.
- Make cluster name mandatory in the watcher and remove the region-wide fallback path.

### 8. Legacy IAM user-policy mode is still kept alive

Evidence:

- `daylily_ec/resources/payload/bin/daylily-ensure-sns-permissions:12-14`
- `daylily_ec/resources/payload/bin/daylily-ensure-sns-permissions:157-165`
- `daylily_ec/resources/payload/bin/daylily-ensure-sns-permissions:181-189`

Why this is legacy:

- The script still supports `--attach-to-user` and documents it as backward-compatible legacy behavior.
- The recommended path is group-based, but the legacy mode is still operational.

Recommended action:

- Remove `--attach-to-user` entirely and keep group-based permission management as the only supported behavior.

## Lower-Priority Cleanup

### 9. Supported docs still document a manual on-node recovery path

Evidence:

- `docs/operations.md:39-45`

Why this is legacy-shaped:

- The doc still says “If the managed login hook has not been applied yet,” then manually `source ./activate` and run `daylily-ec headnode init`.
- That is useful for recovery, but it also preserves an expectation that shell bootstrap may not be fully reliable.

Recommended action:

- Once headnode bootstrap confidence is high enough, replace this with a rerun of the supported operator-side configuration command or a hard failure plus remediation.

## Things That Look Acceptable Today

- The main README and supported docs are otherwise aligned around SSM and `ubuntu`-only access.
- Legacy Bash create logic is quarantined out of the runtime payload rather than being active in the supported create path.
- The real `daylily-ec` lifecycle and the AWS-backed E2E runner are now the dominant supported surfaces.

## Suggested Removal Order

1. Remove/quarantine `init_cloudstackformation.sh` and fix the PEM policy test gap.
2. Remove active compatibility wrappers and the retired experimental staging script from shipped `bin/`.
3. Remove interactive and repo-checkout fallbacks from shipped payload helpers, starting with delete/watch/env helpers.
4. Refactor headnode bootstrap to stop depending on `$HOME/projects/daylily-ephemeral-cluster` and stop mutating shared templates in place.
5. Remove legacy admin modes like `--attach-to-user`.
