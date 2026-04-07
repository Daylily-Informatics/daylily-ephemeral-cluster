# How To Use Codex Desktop On Mac

This is a practical guide to using Codex Desktop on Mac, based on a real session in the `daylily-ephemeral-cluster` repo. The main lesson is simple: treat Codex as a terminal-capable engineering partner with repo context, not as a chatbot that only talks about code.

## What Codex Desktop Was Good At In This Session

In this session, Codex Desktop was especially useful for work that crossed several layers at once:

- debugging environment and bootstrap failures
- tracing import-time and runtime Python errors through the actual repo and installed environment
- updating shell scripts, Python code, tests, and docs together
- handling Git branch, PR, merge, tag, build, and publish steps without leaving the session
- adapting when a tool path changed or a connector token expired

The important point is that the app was not just summarizing code. It was reading the repo, running terminal commands, checking current behavior, making changes, verifying them, and then handling the GitHub and release loop.

## How We Worked Together

The collaboration pattern was consistent, and it is worth copying:

1. You described the problem in concrete terms.
2. Codex inspected the repo and environment before making claims.
3. When the work was broad or risky, Codex proposed a plan first.
4. You either refined the plan or told Codex to implement it.
5. Codex changed code, scripts, and docs in the workspace.
6. Codex ran focused verification, not just static explanation.
7. Codex handled the Git and GitHub flow through branch creation, PR checks, merge, tagging, building, and publishing.

That loop is where the desktop app shines. In one place, it can:

- explore repo state
- read and compare files
- run terminal commands
- edit code
- rerun tests
- watch PR checks
- continue from earlier context without starting over

## Session Walkthrough: What We Actually Did

### 1. Fixing `source ./activate` and the broken `daylily-ec` startup path

**The issue**

The original symptom was a broken `daylily-ec --help` path caused by the wrong executable being found and a missing dependency in the active environment.

**How Codex investigated it**

Codex inspected the repo-local activation flow, the installed console script path, and the environment bootstrap behavior. The important move was not guessing. It checked how `activate` resolved the CLI, where `daylily-ec` was coming from, and why the base environment was being used instead of the intended `DAY-EC` environment.

**What changed**

The `activate` flow was updated so `source ./activate` could bootstrap `DAY-EC` from `environment.yaml` when missing, install the repo into that env, and prefer the environment-local CLI over stale binaries already on `PATH`.

**How it was verified**

Codex used shell checks and targeted activation tests rather than only inspecting the script. It verified both the bootstrap path and the repaired `daylily-ec` command path.

### 2. Repairing runtime and import issues in `DAY-EC`

**The issue**

After the activation path was repaired, the CLI still had startup problems because imports were pulling in more of the system than they should during process startup.

**How Codex investigated it**

Codex followed the import chain from the console entrypoint into `daylily_ec.cli`, through `daylily_ec.__init__`, and into workflow modules. That made it possible to distinguish a shell/bootstrap problem from a Python import-graph problem.

**What changed**

The package init path was made lighter so CLI startup no longer pulled heavyweight workflow code in too early, and compatibility fixes were added for the installed `botocore` shape in the active env.

**How it was verified**

Codex added targeted regression tests and used the real `DAY-EC` flow to verify `daylily-ec version` and related commands in the environment that operators actually use.

### 3. Restoring the cost-estimate and pricing flow with `AWS_PROFILE=lsmc`

**The issue**

The practical user need was not abstract CLI correctness. It was "can I activate and run the pricing / cost-estimate path with my real AWS profile?"

**How Codex investigated it**

Codex used the broken command output as the starting point, then verified the exact operator command path rather than stopping at a unit-test level. That kept the work anchored on the real success case.

**What changed**

The CLI startup path and environment issues were fixed until the pricing flow worked from the same shell operators use after `source ./activate`.

**How it was verified**

The key verification command was:

```bash
source ./activate
AWS_PROFILE=lsmc daylily-ec pricing snapshot --region us-west-2
```

That is an important habit: have Codex prove the real operator command, not just a nearby one.

### 4. Migrating `dyinit` behavior into the CLI-owned headnode flow

**The issue**

The repo still carried legacy `dyinit` behavior and references, but the desired direction was a CLI-owned headnode initialization flow.

**How Codex investigated it**

Codex reviewed the old sourced script, found where `dyinit` was still used, compared that with the new CLI structure, and identified the headnode environment variables and helper behavior that had to remain available.

**What changed**

The session moved headnode initialization into `daylily-ec headnode init`, updated the relevant runtime scripts and payload copies, and standardized the headnode shell bootstrap around:

```bash
source ~/projects/daylily-ephemeral-cluster/activate
eval "$(daylily-ec headnode init --emit-shell --non-interactive)"
```

**How it was verified**

Codex used targeted CLI tests, installer tests, and shell-level checks to confirm that the headnode init path emitted the expected shell context and that active runtime paths no longer depended on the old live flow.

### 5. Moving cluster-create prompts earlier and improving the final output

**The issue**

During cluster creation, budget and heartbeat prompts were appearing after the cluster had already been created. That interrupted the operator experience and made the end of the run feel incomplete.

**How Codex investigated it**

Codex traced the create workflow end to end, found where budget and heartbeat values were being collected, and separated prompt collection from the actual AWS side effects.

**What changed**

The session moved budget and heartbeat input collection earlier, before dry-run and create, while keeping the actual AWS writes after successful create/headnode steps. It also changed the end-of-run output so the final lines are operator-friendly:

- second-to-last line: the exact login or fallback command
- last line: `...fin!`
- optional macOS speech cue if `say` exists

**How it was verified**

Codex added workflow tests for prompt timing, reused values, fallback output, and final-line ordering. This is a good example of asking Codex to verify behavior, not just code paths.

### 6. Hardening `install_miniconda` for modern Macs

**The issue**

`bin/install_miniconda` was failing on newer Macs, and the failure was not just one thing. There was a real `set -u` bug around `MACHINE`, and the script assumed `wget` was present.

**How Codex investigated it**

Codex ran the machine-detection logic in clean `zsh` and clean `bash`, confirmed that the architecture mapping itself was fine on this Mac, and then isolated the actual bug in the script logic.

**What changed**

The installer was updated to:

- avoid crashing on unset `MACHINE`
- detect Apple Silicon, Intel macOS, Linux x86_64, and Linux ARM explicitly
- prefer `curl -fsSL`
- fall back to `wget -q`
- keep the payload mirror in sync

**How it was verified**

Codex added shell-level tests that used fake `uname`, fake downloaders, and a fake installer payload so the logic could be proven without mutating the real machine.

### 7. Updating docs, opening a PR, waiting for green, merging, tagging, building, and publishing

**The issue**

Once behavior changed, the operator docs needed to match. After that, the repo needed a full publish cycle, not just a local code change.

**How Codex investigated it**

Codex searched the active docs for stale activation, cluster-create, and headnode guidance, updated only the live docs, then used the repo's real Git/GitHub/release flow.

**What changed**

The session updated the active operator docs, opened PRs, watched checks, merged to `main`, cut release tags, built distributions, and published to PyPI.

One useful real-world detail: the GitHub app connector token expired during PR creation, so Codex fell back to the authenticated `gh` CLI instead of getting stuck.

**How it was verified**

Verification here was procedural:

- targeted tests before PR
- green PR checks before merge
- local `main` sync after merge
- clean `dist/` rebuild
- successful `twup` publish

## Practical Commands From The Session

These are the commands that mattered most in the working pattern:

```bash
source ./activate
daylily-ec version
AWS_PROFILE=lsmc daylily-ec pricing snapshot --region us-west-2
python3 -m pytest -q tests/test_workflow.py tests/test_install_miniconda.py
gh pr checks 235 --watch --interval 15
git tag -a v1.1.0 -m "v1.1.0"
python -m build
twup
```

A few good habits are embedded in that list:

- activate the repo-local environment first
- verify the exact operator command you care about
- run narrow tests when the change is narrow
- let Codex watch PR checks instead of polling by hand
- keep release steps explicit

## How To Use Codex Desktop Well On Mac

The main practical lessons from this session were:

### Ask for a plan when the work is broad

When the work spans shell bootstrap, Python code, tests, docs, PR flow, and release steps, ask Codex for a written plan first. That gave us stable checkpoints for the bigger changes.

### Let Codex inspect the real repo before it answers

The best results came when Codex read scripts, searched the tree, ran the real commands, and traced actual failures. The worst results in tools like this usually come from guessing too early.

### Ask Codex to implement, not just explain

Once the plan looked right, the fastest path was explicit: implement this plan. That kept the session moving from diagnosis into actual edits and verification.

### Demand focused verification

A useful pattern is: "fix it, then prove it with the exact command I care about." In this session that mattered for activation, pricing, headnode bootstrap, PR checks, and publishing.

### Use Codex for the full Git flow when you want it

The app was useful not just for local code changes but for:

- creating a feature branch
- staging and committing
- pushing
- opening a PR
- waiting for checks
- merging
- tagging
- building
- publishing

If you want end-to-end help, say so explicitly.

### Keep release steps explicit

Codex can do release work, but it works best when the release contract is concrete: merge to `main`, tag this version, rebuild `dist/`, reload shell config, run `twup`.

### Expect tool and environment wrinkles

Desktop coding sessions are real environments. Connectors expire. Shell aliases differ. Local envs drift. The right move is usually not to stop. It is to adapt and keep the workflow grounded in the actual machine.

## Real-World Wrinkles To Expect

These were not theoretical. They happened in this session:

- stale conda envs and missing Python packages
- repo code and installed package state getting out of sync
- `daylily-ec` working in the repo but not in the old installed path
- GitHub connector auth expiry, with `gh` as the fallback
- `.zshrv` not existing as a command even though the release step referred to it
- Mac bootstrap assumptions breaking because `curl` existed but `wget` might not

This is exactly why Codex Desktop is useful: it can keep going through those edges instead of leaving you with a half-finished answer.

## Cautions And Safety Habits

Some habits are worth making explicit:

- Keep destructive cloud actions explicit.
- If AWS changes are risky, ask Codex to inspect, dry-run, or plan first.
- Verify before merge.
- Verify again before publish.
- Prefer small, checkable steps over "fix everything" asks when the blast radius is unclear.
- When you do want broad work, ask for a plan and then approve implementation.

In other words: use Codex aggressively, but not vaguely.

## Closing

The practical takeaway is that Codex Desktop works best when you use it like a disciplined engineering partner with terminal access, repo context, and a clear verification contract. In this session, that meant we were able to move from a broken local CLI, through environment and headnode fixes, into doc cleanup, PR management, and release publishing without leaving the app or losing the thread.

That is the real value: not just code generation, but sustained technical work with context, tools, and follow-through.
