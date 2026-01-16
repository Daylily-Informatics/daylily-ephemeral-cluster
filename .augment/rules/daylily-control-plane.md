---
type: "always_apply"
---

# Daylily control-plane refactor rules (authoritative DynamoDB)

## Hard constraints (do not violate)
- Keep ParallelCluster + tmux runner architecture (no Step Functions / Batch rewrite).
- DynamoDB is authoritative for: state machine, locking/ownership, customer_id, run parameters, metrics/progress.
- S3 workset folder is artifact storage + optional compatibility interface for legacy monitor.
- DO NOT implement a real dy-r pipeline run. Keep dy-r in the template as "-p help" or equivalent placeholder.
- Do not move/rename legacy scripts; add new worker script alongside existing monitor.
- Minimize schema migration: prefer additive DynamoDB attributes.

## Behavioral requirements
- Locking is separate from state. State should remain: READY / IN_PROGRESS / COMPLETE / ERROR (plus any existing states for backward compat).
- release_lock() must NOT change state. It only clears lock fields if lock_owner matches.
- Worker/monitor must acquire DynamoDB lock before writing any S3 lock sentinel.
- API customer ownership checks must be based on customer_id (not bucket equality).

## Acceptance criteria
- Unit tests updated; `pytest` passes.
- New bin/daylily-workset-worker exists and processes from DynamoDB.
- create_customer_workset writes records to control bucket/prefix, not customer data bucket.
- Progress/metrics are written into DynamoDB in a structured way.
