#!/usr/bin/env python3
"""Materialize the eleven receipt-verified pclu-18045 delivery records.

This is a one-off, deterministic ledger companion.  It reads only exported
status objects and local FSx-export receipts, refuses any non-RC0 or
non-successful-delivery evidence, updates the current catalog text without
reserializing unrelated historical entries, and freezes the same current view
as DYEC 18.0.58.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "config/daylily_pipeline_command_catalog.yaml"
PAYLOAD_CATALOG = ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
LEDGER = "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger.md"
RECORDS_PATH = Path(__file__).with_name("catalog_evidence_records.json")
S3_PREFIX = "s3://lsmc-ssf-sequencing-data/derived/pclu-18045"


LANES = (
    {
        "command_id": "illumina_run_qc",
        "analysis_id": "pclu18045_ilmn_runqc_18047_15027_20260818t1803z",
        "dayec_tag": "18.0.47",
        "dayec_commit": "6c034972727769ddc376791d15ddd1a76f84f019",
        "dayoa_tag": "15.0.27",
        "dayoa_commit": "41c7f1c9b36fe6166337817133fc271923fc085f",
        "export_task": "task-0bb6871b1e2d50c35",
        "export_dra": "dra-0de1482aefbbc52fa",
        "receipt": "docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ilmn_runqc_18047_15027_20260818t1803z/fsx_export.yaml",
    },
    {
        "command_id": "ont_run_qc",
        "analysis_id": "pclu18045_ont_runqc_18047_15027_20260818t1743z",
        "dayec_tag": "18.0.47",
        "dayec_commit": "6c034972727769ddc376791d15ddd1a76f84f019",
        "dayoa_tag": "15.0.27",
        "dayoa_commit": "41c7f1c9b36fe6166337817133fc271923fc085f",
        "export_task": "task-04c2d9004a10fe4d9",
        "export_dra": "dra-0f4fe41322138dfee",
        "receipt": "docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ont_runqc_18047_15027_20260818t1743z/fsx_export.yaml",
    },
    {
        "command_id": "ultima_run_qc",
        "analysis_id": "pclu18045_ultima_runqc_18047_15027_20260818t1825z",
        "dayec_tag": "18.0.47",
        "dayec_commit": "6c034972727769ddc376791d15ddd1a76f84f019",
        "dayoa_tag": "15.0.27",
        "dayoa_commit": "41c7f1c9b36fe6166337817133fc271923fc085f",
        "export_task": "task-0cc1b2ddc22746cf5",
        "export_dra": "dra-0aed628e5e9c676fe",
        "receipt": "docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ultima_runqc_18047_15027_20260818t1825z/fsx_export.yaml",
    },
    {
        "command_id": "hiomr2_slim_kitchensink_mega",
        "analysis_id": "pclu18045_rc0_18052_hiomr2_20260819T004600Z",
        "dayec_tag": "18.0.52",
        "dayec_commit": "96ddaa0c066a64ea703bc5313a4f1c8c93f5290e",
        "dayoa_tag": "15.0.29",
        "dayoa_commit": "07aff68545687a4c7b29d570993613dacdc15bad",
        "export_task": "task-05709df38186d168a",
        "export_dra": "dra-096d62f568ab913df",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-04-hiomr2/fsx_export.yaml",
    },
    {
        "command_id": "inflection-bjuice-product-v0.9",
        "analysis_id": "pclu18045_rc0_18052_bjuice_20260819T004600Z",
        "dayec_tag": "18.0.52",
        "dayec_commit": "96ddaa0c066a64ea703bc5313a4f1c8c93f5290e",
        "dayoa_tag": "15.0.29",
        "dayoa_commit": "07aff68545687a4c7b29d570993613dacdc15bad",
        "export_task": "task-06be83f0601a7e82a",
        "export_dra": "dra-08f8548757bfb61f5",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-05-bjuice/fsx_export.yaml",
    },
    {
        "command_id": "illumina_hg002_kitchensink_multiqc",
        "analysis_id": "pclu18045_rc0_18052_soloilmn_20260819T004600Z",
        "dayec_tag": "18.0.52",
        "dayec_commit": "96ddaa0c066a64ea703bc5313a4f1c8c93f5290e",
        "dayoa_tag": "15.0.29",
        "dayoa_commit": "07aff68545687a4c7b29d570993613dacdc15bad",
        "export_task": "task-0bd1d9ee8fe48137c",
        "export_dra": "dra-02fed7c06c975ae16",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-06-solo-ilmn/fsx_export.yaml",
    },
    {
        "command_id": "ont_snv_alignstats_kitchensink",
        "analysis_id": "pclu18045_rc0_18052_soloont_20260819T004600Z",
        "dayec_tag": "18.0.52",
        "dayec_commit": "96ddaa0c066a64ea703bc5313a4f1c8c93f5290e",
        "dayoa_tag": "15.0.29",
        "dayoa_commit": "07aff68545687a4c7b29d570993613dacdc15bad",
        "export_task": "task-022cb6e9cf3140dff",
        "export_dra": "dra-0706b4324d3e946b0",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-07-solo-ont/fsx_export.yaml",
    },
    {
        "command_id": "ultima_snv_alignstats_kitchensink",
        "analysis_id": "pclu18045_rc0_18052_soloultima_20260819T004600Z",
        "dayec_tag": "18.0.52",
        "dayec_commit": "96ddaa0c066a64ea703bc5313a4f1c8c93f5290e",
        "dayoa_tag": "15.0.29",
        "dayoa_commit": "07aff68545687a4c7b29d570993613dacdc15bad",
        "export_task": "task-005ba3c2b1186e132",
        "export_dra": "dra-07b88b4df6d0232a6",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-08-solo-ultima/fsx_export.yaml",
    },
    {
        "command_id": "complete_genomics_cg_snv_concordance",
        "analysis_id": "pclu18045_rc0_18052_solocg_20260819T004600Z",
        "dayec_tag": "18.0.52",
        "dayec_commit": "96ddaa0c066a64ea703bc5313a4f1c8c93f5290e",
        "dayoa_tag": "15.0.29",
        "dayoa_commit": "07aff68545687a4c7b29d570993613dacdc15bad",
        "export_task": "task-0328db6d15f94b0bd",
        "export_dra": "dra-0068679f14941e110",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-09-solo-cg/fsx_export.yaml",
    },
    {
        "command_id": "illumina_sentieon_pangenome_kitchensink",
        "analysis_id": "pclu18045_rc0_18053_pangenomeilmn_20260819T033638Z",
        "dayec_tag": "18.0.53",
        "dayec_commit": "3f41a6b4842d55e9eef7942816daa48e85cb2ba0",
        "dayoa_tag": "15.0.30",
        "dayoa_commit": "65c45c74e922c276eeb676ed6ed24bfae7fbe859",
        "export_task": "task-0a564cfaa7a78831b",
        "export_dra": "dra-0399a694ff79bf48a",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-10-pangenome-ilmn/fsx_export.yaml",
    },
    {
        "command_id": "ultima_sentieon_pangenome_kitchensink",
        "analysis_id": "pclu18045_rc0_18055_pangenomeultima_20260819T051914Z",
        "dayec_tag": "18.0.55",
        "dayec_commit": "1358b349edb6f7a6fc88d2ff87c8ce79197ed89c",
        "dayoa_tag": "15.0.35",
        "dayoa_commit": "24edfc39895e9dddfcd26738930a863ba938921f",
        "export_task": "task-078777327e77d1b96",
        "export_dra": "dra-05be422bf08c53c66",
        "receipt": "docs/plans/20260819T070143Z_pclu_18045_rc0_export_and_evidence_ledger_artifacts/EXP-11-pangenome-ultima/fsx_export.yaml",
    },
)


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def status_payload(s3_uri: str) -> dict:
    raw = subprocess.check_output(
        ["aws", "s3", "cp", "--profile", "lsmc", "--region", "us-west-2", s3_uri, "-"],
        text=True,
    )
    return json.loads(raw)


def validated_record(lane: dict, generated_at: str) -> dict:
    analysis_id = lane["analysis_id"]
    s3_root = f"{S3_PREFIX}/{analysis_id}/"
    status_uri = f"{s3_root}daylily-omics-analysis/status.json"
    status = status_payload(status_uri)
    attempts = status.get("attempts", [])
    dry = [attempt for attempt in attempts if attempt.get("mode") in {"dry", "dry_run"}]
    live = [attempt for attempt in attempts if attempt.get("mode") == "live"]
    if not dry or not live:
        raise RuntimeError(f"{analysis_id}: missing dry or live status attempt")
    dry_attempt, live_attempt = dry[-1], live[-1]
    for label, attempt in (("dry", dry_attempt), ("live", live_attempt)):
        controller = attempt.get("controller", {})
        day_run = attempt.get("day_run", {})
        if attempt.get("state") != "succeeded" or controller.get("exit_code") != 0 or day_run.get("exit_code") != 0:
            raise RuntimeError(f"{analysis_id}: {label} controller/day-run is not RC0")
    if live_attempt.get("snakemake", {}).get("exit_code") != 0:
        raise RuntimeError(f"{analysis_id}: live Snakemake receipt is not RC0")

    receipt_path = ROOT / lane["receipt"]
    receipt = yaml.safe_load(receipt_path.read_text(encoding="utf-8"))["fsx_export"]
    expected_receipt = {
        "status": "success",
        "phase": "complete",
        "task_id": lane["export_task"],
        "association_id": lane["export_dra"],
        "task_lifecycle": "SUCCEEDED",
        "detached": True,
        "delete_data_in_file_system": False,
        "s3_root": s3_root,
    }
    for key, expected in expected_receipt.items():
        if receipt.get(key) != expected:
            raise RuntimeError(f"{analysis_id}: export receipt {key}={receipt.get(key)!r}, expected {expected!r}")
    if receipt.get("clone_status_v2_evidence", {}).get("verified") is not True:
        raise RuntimeError(f"{analysis_id}: clone-status-v2 evidence is not verified")

    notes = (
        "Fresh pclu-18045 same-root dry/live controller evidence: dry controller/day-run rc=0; "
        "live controller/day-run/Snakemake rc=0. Full-root export task "
        f"{lane['export_task']} succeeded, detached {lane['export_dra']}, preserved FSx, and clone-status-v2 "
        "status evidence was re-HEADed. Direct delivery provenance only; the actual execution DayOA tag is retained "
        "and does not assert execution at the current 15.0.37 catalog pin."
    )
    return {
        "run_id": analysis_id,
        "generated_at": generated_at,
        "report_path": status_uri,
        "ledger_path": LEDGER,
        "cluster": "pclu-18045",
        "region": "us-west-2",
        "region_az": "unrecorded",
        "dayec_tag": lane["dayec_tag"],
        "dayec_commit": lane["dayec_commit"],
        "dayoa_tag": lane["dayoa_tag"],
        "dayoa_commit": lane["dayoa_commit"],
        "tested_command": live_attempt["controller"]["command"],
        "status": "success",
        "dryrun_status": "success",
        "live_status": "success",
        "dryrun_analysis_id": analysis_id,
        "live_analysis_id": analysis_id,
        "stage_or_context": s3_root,
        "failure_cause": "",
        "notes": notes,
        "export_receipt": lane["receipt"],
        "export_task": lane["export_task"],
        "export_dra": lane["export_dra"],
    }


def validation_fragment(record: dict) -> str:
    fields = (
        "run_id",
        "generated_at",
        "report_path",
        "ledger_path",
        "cluster",
        "region",
        "region_az",
        "dayec_tag",
        "dayec_commit",
        "dayoa_tag",
        "dayoa_commit",
        "tested_command",
        "status",
        "dryrun_status",
        "live_status",
        "dryrun_analysis_id",
        "live_analysis_id",
        "stage_or_context",
        "failure_cause",
        "notes",
    )
    lines = [f"        - {fields[0]}: {quoted(record[fields[0]])}"]
    lines.extend(f"          {field}: {quoted(record[field])}" for field in fields[1:])
    return "\n".join(lines) + "\n"


def update_command(current_block: str, record: dict) -> str:
    command_id = record["command_id"]
    start_match = re.search(rf"^      {re.escape(command_id)}:\n", current_block, re.MULTILINE)
    if start_match is None:
        raise RuntimeError(f"current catalog lacks command {command_id}")
    start = start_match.start()
    next_match = re.search(r"^(?:      [^ \n][^:\n]*:\n|    aliases:)", current_block[start + 1 :], re.MULTILINE)
    if next_match is None:
        raise RuntimeError(f"could not delimit current command {command_id}")
    end = start + 1 + next_match.start()
    command_block = current_block[start:end]
    s3_root = record["stage_or_context"]

    # This must precede evidence-prefix replacement because the delivery root
    # deliberately contains the analysis/run identifier.
    if record["run_id"] in command_block:
        raise RuntimeError(f"{command_id}: record already exists")

    evidence_pattern = re.compile(r"^        validation_evidence_s3_uri_prefix:.*\n", re.MULTILINE)
    if evidence_pattern.search(command_block):
        command_block = evidence_pattern.sub(
            f"        validation_evidence_s3_uri_prefix: {s3_root}\n", command_block, count=1
        )
    else:
        validated_match = re.search(r"^(        validated_version:.*\n)", command_block, re.MULTILINE)
        if validated_match is None:
            raise RuntimeError(f"{command_id}: lacks validated_version")
        insertion = f"        validation_evidence_s3_uri_prefix: {s3_root}\n"
        command_block = command_block[: validated_match.end()] + insertion + command_block[validated_match.end() :]

    fragment = validation_fragment(record)
    empty_runs = re.search(r"^        validation_runs: \[\]\n", command_block, re.MULTILINE)
    if empty_runs:
        command_block = (
            command_block[: empty_runs.start()]
            + "        validation_runs:\n"
            + fragment
            + command_block[empty_runs.end() :]
        )
    else:
        runs_match = re.search(r"^        validation_runs:\n", command_block, re.MULTILINE)
        if runs_match is None:
            repository_match = re.search(
                r"^        repository: daylily-omics-analysis\n", command_block, re.MULTILINE
            )
            if repository_match is None:
                raise RuntimeError(f"{command_id}: lacks validation_runs and repository anchor")
            command_block = (
                command_block[: repository_match.start()]
                + "        validation_runs:\n"
                + fragment
                + command_block[repository_match.start() :]
            )
        else:
            next_property = re.search(r"^        [A-Za-z_][^:\n]*:", command_block[runs_match.end() :], re.MULTILINE)
            if next_property is None:
                raise RuntimeError(f"{command_id}: cannot delimit validation_runs")
            insertion_at = runs_match.end() + next_property.start()
            command_block = command_block[:insertion_at] + fragment + command_block[insertion_at:]

    return current_block[:start] + command_block + current_block[end:]


def main() -> None:
    source_text = CATALOG.read_text(encoding="utf-8")
    payload_text = PAYLOAD_CATALOG.read_text(encoding="utf-8")
    if source_text != payload_text:
        raise RuntimeError("source and packaged catalog copies differ before update")
    if re.search(r"^  18\.0\.57:\n", source_text, re.MULTILINE):
        raise RuntimeError("18.0.58 snapshot already exists")

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    records = [validated_record(dict(lane), generated_at) for lane in LANES]
    for record in records:
        record["command_id"] = next(
            lane["command_id"] for lane in LANES if lane["analysis_id"] == record["run_id"]
        )

    start = source_text.index("\n  current:\n") + 1
    next_version = re.search(r"^  \d+\.\d+\.\d+:\n", source_text[start + 1 :], re.MULTILINE)
    if next_version is None:
        raise RuntimeError("could not delimit current catalog block")
    end = start + 1 + next_version.start()
    current_block = source_text[start:end]
    for record in records:
        current_block = update_command(current_block, record)
    if not current_block.startswith("  current:\n"):
        raise RuntimeError("updated current catalog boundary is invalid")
    snapshot = current_block.replace("  current:\n", "  18.0.58:\n", 1)
    new_text = source_text[:start] + current_block + source_text[end:]
    if not new_text.endswith("\n"):
        new_text += "\n"
    new_text += snapshot

    # Parse before writing; this catches textual-boundary mistakes without
    # reserializing or mutating unrelated catalog history.
    parsed = yaml.safe_load(new_text)
    current = parsed["dyec_builds"]["current"]
    frozen = parsed["dyec_builds"]["18.0.58"]
    if current != frozen:
        raise RuntimeError("18.0.58 snapshot does not exactly match current")
    for record in records:
        command = current["commands"][record["command_id"]]
        if command["git_tag"] != "15.0.37":
            raise RuntimeError(f"{record['command_id']}: current catalog pin changed")
        if command["validation_evidence_s3_uri_prefix"] != record["stage_or_context"]:
            raise RuntimeError(f"{record['command_id']}: evidence URI mismatch")
        if command["validation_runs"][-1]["run_id"] != record["run_id"]:
            raise RuntimeError(f"{record['command_id']}: latest validation run mismatch")

    CATALOG.write_text(new_text, encoding="utf-8")
    PAYLOAD_CATALOG.write_text(new_text, encoding="utf-8")
    RECORDS_PATH.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "catalog_sha256": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
                "records": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"updated {len(records)} records; catalog_sha256={hashlib.sha256(new_text.encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
