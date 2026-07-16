# Analysis-Root Agent Locking

This is the shared coordination contract for `/fsx/analysis_results/**` roots. It is designed for Codex, shell users, and other agents to use the same files and commands before touching a running or resumable analysis.

## Policy

Allowed without owning the write lock:

- query, search, monitor, and log review
- S3 export without FSx deletion
- visit logging

Requires owning the write lock:

- live workflow writes
- `dy-r --unlock`
- edits, touches, moves, or deletes in the analysis root
- local FSx cleanup
- job kill or cancel tied to the analysis root
- DRA detach or cluster teardown tied to the analysis root

Takeover is never automatic. A takeover requires a token request, explicit human approval, and a recorded reason.

## Metadata Layout

Each analysis root gets:

```text
<analysis_root>/.dayoa_agent/owner.json
<analysis_root>/.dayoa_agent/write.lock/
<analysis_root>/.dayoa_agent/write.lock/owner.json
<analysis_root>/.dayoa_agent/write.lock/heartbeat.jsonl
<analysis_root>/.dayoa_agent/visits/YYYYMMDD.jsonl
<analysis_root>/.dayoa_agent/takeovers.jsonl
/fsx/analysis_results/.dayoa_agent_visits/YYYYMMDD.jsonl
```

The write lock is acquired with atomic `mkdir <analysis_root>/.dayoa_agent/write.lock`.

## Agent Identity

Long-running agents should set a stable identity before acquiring a lock:

```bash
export DAYOA_AGENT_ID="codex-<thread-or-session-id>"
export DAYOA_AGENT_KIND="codex"
export DAYOA_HUMAN_REQUESTOR="jmajor"
export DAYOA_TMUX_SESSION="<tmux-session-name>"
export DAYOA_LEDGER_PATH="/path/to/docs/plans/<ledger>.md"
```

If `DAYOA_AGENT_ID` is absent, DYEC records the best available identity from Codex, tmux, or `user@host`. Explicit `DAYOA_AGENT_ID` is preferred because acquire, heartbeat, guard, and release may happen in separate shell processes.

## Commands

Record a read visit:

```bash
dyec analysis visit \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --mode read \
  --intent "inspect logs before status report" \
  --note "no writes"
```

Record a no-delete export visit, optionally mirrored to the S3 report/export prefix:

```bash
dyec analysis visit \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --mode export \
  --intent "S3 snapshot export without FSx cleanup" \
  --s3-visit-uri s3://bucket/prefix/for/export/
```

Acquire a write lock before a live controller:

```bash
dyec analysis lock acquire \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --operation write \
  --intent "live dy-r workflow" \
  --command-summary "dy-r produce_multiqc_all -p -k -j 100"
```

Check the current owner:

```bash
dyec analysis lock status --analysis-root /fsx/analysis_results/ubuntu/<analysis_id>
```

Guard a protected shell command:

```bash
dyec analysis guard \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --operation kill \
  --intent "approved cancellation of stale controller" \
  -- scancel <jobid>
```

Release the current agent's lock:

```bash
dyec analysis lock release \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --note "workflow terminal and final export verified"
```

## Takeover

First request a takeover token and show the current owner to the user:

```bash
dyec analysis lock takeover \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --operation write \
  --reason "previous Codex session is no longer active" \
  --request
```

Only after explicit human approval, use the printed token:

```bash
dyec analysis lock takeover \
  --analysis-root /fsx/analysis_results/ubuntu/<analysis_id> \
  --operation write \
  --reason "explicit double-approved takeover from inactive owner" \
  --approved-by "jmajor" \
  --confirm-token <token> \
  --intent "resume live workflow"
```

## DayOA Wrapper Behavior

When `DAY_ROOT` is under `/fsx/analysis_results/**`, `dy-r` now calls DYEC before Snakemake:

- dry-run/status commands write a `read` visit and do not require the write lock.
- live workflow commands require the current agent to own the `write` lock.
- `dy-r --unlock` requires the current agent to own a lock and records the `unlock` operation.
- dry-runs no longer install the raw Snakemake unlock trap.

Raw shell `rm`, `scancel`, and process kills cannot be fully blocked without broader cluster shell policy. Agents must use `dyec analysis guard` for those actions so the owner check and visit logs are authoritative.
