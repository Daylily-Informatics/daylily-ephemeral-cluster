"""Strict `sacct --parsable2` adapter for cost-center allocation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping


SACCT_FIELDS = (
    "JobIDRaw",
    "JobID",
    "User",
    "Account",
    "Comment",
    "JobName",
    "Partition",
    "State",
    "Submit",
    "Eligible",
    "Start",
    "End",
    "ElapsedRaw",
    "NodeList",
    "AllocNodes",
    "AllocCPUS",
    "NCPUS",
    "ExitCode",
)


class SacctParseError(RuntimeError):
    """Raised when sacct output cannot be trusted for accounting."""


@dataclass(frozen=True)
class SacctJobRecord:
    job_id_raw: str
    job_id: str
    user: str
    account: str
    cost_center: str
    job_name: str
    partition: str
    state: str
    submit_at: str
    eligible_at: str
    start_at: str
    end_at: str
    elapsed_seconds: int
    node_list_raw: str
    node_names: tuple[str, ...]
    alloc_nodes: int
    alloc_cpus: int
    ncpus: int
    exit_code: str
    cluster: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id_raw": self.job_id_raw,
            "job_id": self.job_id,
            "user": self.user,
            "account": self.account,
            "cost_center": self.cost_center,
            "job_name": self.job_name,
            "partition": self.partition,
            "state": self.state,
            "submit_at": self.submit_at,
            "eligible_at": self.eligible_at,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "elapsed_seconds": self.elapsed_seconds,
            "node_list_raw": self.node_list_raw,
            "node_names": list(self.node_names),
            "alloc_nodes": self.alloc_nodes,
            "alloc_cpus": self.alloc_cpus,
            "ncpus": self.ncpus,
            "exit_code": self.exit_code,
            "cluster": self.cluster,
        }


def sacct_command(start_utc: str, end_utc: str) -> str:
    fields = ",".join(SACCT_FIELDS)
    return (
        "TZ=UTC sacct -P -n --allocations --allusers "
        f"--starttime {start_utc} --endtime {end_utc} --format={fields}"
    )


def parse_sacct_parsable2(
    text: str,
    *,
    node_expansions: Mapping[str, list[str] | tuple[str, ...]] | None = None,
    cluster: str = "",
) -> list[SacctJobRecord]:
    expansions = node_expansions or {}
    records: list[SacctJobRecord] = []
    field_count = len(SACCT_FIELDS)
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\n")
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != field_count:
            raise SacctParseError(
                f"sacct row {line_number} has {len(parts)} fields, expected {field_count}."
            )
        values = dict(zip(SACCT_FIELDS, parts))
        if _is_job_step_row(values["JobIDRaw"]) or _is_job_step_row(values["JobID"]):
            continue
        comment = values["Comment"].strip()
        if not comment:
            raise SacctParseError(f"sacct row {line_number} is missing required Comment.")
        if any(ch.isspace() for ch in comment) or "|" in comment:
            raise SacctParseError(f"sacct row {line_number} has malformed Comment '{comment}'.")
        raw_nodelist = values["NodeList"].strip()
        nodes = tuple(expansions.get(raw_nodelist, (raw_nodelist,))) if raw_nodelist else ()
        records.append(
            SacctJobRecord(
                job_id_raw=values["JobIDRaw"],
                job_id=values["JobID"],
                user=values["User"],
                account=values["Account"],
                cost_center=comment,
                job_name=values["JobName"],
                partition=values["Partition"],
                state=values["State"],
                submit_at=_normalize_time(values["Submit"]),
                eligible_at=_normalize_time(values["Eligible"]),
                start_at=_normalize_time(values["Start"]),
                end_at=_normalize_time(values["End"]),
                elapsed_seconds=_parse_int(values["ElapsedRaw"], field="ElapsedRaw"),
                node_list_raw=raw_nodelist,
                node_names=nodes,
                alloc_nodes=_parse_int(values["AllocNodes"], field="AllocNodes"),
                alloc_cpus=_parse_int(values["AllocCPUS"], field="AllocCPUS"),
                ncpus=_parse_int(values["NCPUS"], field="NCPUS"),
                exit_code=values["ExitCode"],
                cluster=cluster,
            )
        )
    return records


def _is_job_step_row(job_id: str) -> bool:
    return "." in str(job_id or "")


def _parse_int(value: str, *, field: str) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError as exc:
        raise SacctParseError(f"{field} must be an integer, got '{value}'.") from exc


def _normalize_time(value: str) -> str:
    text = str(value or "").strip()
    if not text or text in {"Unknown", "None"}:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")
        except ValueError as exc:
            raise SacctParseError(f"Invalid sacct timestamp '{value}'.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
