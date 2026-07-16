# DYEC 10.0.118 Headnode Update Ledger

Started: 2026-07-08T14:01:50Z
Operator: Codex
Requestor: jmajor

## Objective

Update the local DAY-EC checkout and the `jul8itelx4` and `ifx-hyb-all`
clusters to DYEC `10.0.118`; verify `conda activate DAY-EC` plus `dyec`
version output on each cluster; update DayOA environment/config where present
to DayOA `10.0.70` or `10.0.69`; verify the `daylily-omics-analysis` clone
source resolves to the `lsmc-bio` fork.

## Gates

| ID | Scope | Action | Status | Evidence | Notes |
| --- | --- | --- | --- | --- | --- |
| G0 | Local DYEC | Baseline local repo status and tags | SUCCESS | `git status --short --branch` -> `jem-dev...origin/jem-dev [ahead 1]`; newest local tag `10.0.117` before fetch. | Worktree clean at start. |
| L1 | Local DYEC | Fetch/update local checkout to DYEC `10.0.118` | SUCCESS | `git fetch origin jem-dev --tags`; `HEAD=3621b79b`, tag points at HEAD: `10.0.118`; `dyec --json version` -> `10.0.118`; operator config `~/.config/daylily/daylily_cli_global.yaml` pins `git_ephemeral_cluster_repo_tag: 10.0.118`. | Local repo has only this ledger untracked/dirty; tagged source itself is clean. |
| H1 | jul8itelx4 | Configure headnode DAY-EC `10.0.118` | SUCCESS | `dyec headnode configure --profile lsmc --region us-west-2 --cluster jul8itelx4` -> `Headnode configured via SSM`; headnode `i-02946c880916d6dbc`; verification SSM command `076db7d6-e9f9-4aa6-b470-5f82badfe984`. | First post-config verification command `845276cf-626e-4ad4-b1ef-ac0bf7458183` updated config/DayOA but failed at `day-clone --list` because base conda Python lacked PyYAML; fixed by installing PyYAML into base conda Python, then verification succeeded. |
| H2 | ifx-hyb-all | Configure headnode DAY-EC `10.0.118` | SUCCESS | `dyec headnode configure --profile lsmc --region us-west-2 --cluster ifx-hyb-all` -> `Headnode configured via SSM`; headnode `i-06e1d58f8bc1bd150`; verification SSM command `f287475e-9d91-41f2-8922-b1e932cb3711`. |  |
| D1 | jul8itelx4 | Verify/update DayOA env/config to `10.0.70` or `10.0.69` and lsmc-bio clone source | SUCCESS | `CONDA_DEFAULT_ENV=DAY-EC`; `dyec --json version` -> `10.0.118`; DayOA package `10.0.67` -> `10.0.70`; no separate DayOA conda envs found; `day-clone --list` shows `daylily-omics-analysis` default ref `10.0.70`; catalog `https_url=https://github.com/lsmc-bio/daylily-omics-analysis.git`, `ssh_url=git@github.com:lsmc-bio/daylily-omics-analysis.git`, `relative_path=daylily-omics-analysis`, command git tags `10.0.70`. | User-level global config also pins `git_ephemeral_cluster_repo_tag=10.0.118`. |
| D2 | ifx-hyb-all | Verify/update DayOA env/config to `10.0.70` or `10.0.69` and lsmc-bio clone source | SUCCESS | `CONDA_DEFAULT_ENV=DAY-EC`; `dyec --json version` -> `10.0.118`; DayOA package already `10.0.69`; no separate DayOA conda envs found; `day-clone --list` shows `daylily-omics-analysis` default ref `10.0.70`; catalog `https_url=https://github.com/lsmc-bio/daylily-omics-analysis.git`, `ssh_url=git@github.com:lsmc-bio/daylily-omics-analysis.git`, `relative_path=daylily-omics-analysis`, command git tags `10.0.70`. | User-level global config also pins `git_ephemeral_cluster_repo_tag=10.0.118`. |
| F1 | Final | Report terminal rows and residual blockers | SUCCESS | All cluster rows terminal. | No destructive AWS actions, no Slurm/job actions. |
