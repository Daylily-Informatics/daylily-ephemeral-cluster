#!/usr/bin/env python3
"""Operational helper for the jul8itelx4 DYEC 10.0.118 catalog run."""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell
from daylily_ec.repositories import AnalysisCommand, load_repository_catalog
from daylily_ec.run_mounts import MOUNT_PURPOSE_RUN, list_run_mounts, normalize_s3_uri
from daylily_ec.tests_runner import (
    catalog_role_uris,
    default_stage_func,
    generated_config_paths,
    render_catalog_dy_command,
    run_id_from_source,
    run_platform,
    run_profile_source,
    write_run_context,
    write_sample_manifest,
)


STAMP = "20260708T142032Z"
RUN_STAMP = "20260708T152112Z"
RUN_STAMP_OVERRIDES = {
    "illumina_snv_alignstats": "20260708T150500Z",
    "ultima_run_qc": "20260708T163200Z",
}
CLUSTER = "jul8itelx4"
REGION = "us-west-2"
PROFILE = "lsmc"
DAYOA_TAG = "10.0.70"
JOBS = 300
EXECUTING_ENTITY = "ubuntu"
HEADNODE_INSTANCE_ID = "i-02946c880916d6dbc"
LEDGER_PATH = (
    "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
    "20260708T142032Z_intel_catalog_bjuice_jul8itelx4_dyec_10_0_118_ledger.md"
)
EVIDENCE_ROOT = (
    "s3://lsmc-ssf-sequencing-data/derived/jul8itelx4/"
    "command_catalog_results/10.0.70-20260708T142032Z/"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "docs" / "plans" / f"{STAMP}_intel_catalog_bjuice_runtime"
CATALOG_PATH = REPO_ROOT / "config" / "daylily_pipeline_command_catalog.yaml"
SELECTED_JSON = (
    REPO_ROOT
    / "docs"
    / "plans"
    / f"{STAMP}_intel_catalog_bjuice_selected_commands.json"
)


def selected_commands() -> list[AnalysisCommand]:
    catalog = load_repository_catalog(CATALOG_PATH)
    return [
        cmd
        for cmd in catalog.commands()
        if (cmd.type == "prod" and "daywgs" in cmd.compatible_cluster_types)
        or cmd.command_id == "inflection-bjuice-product-v0.1"
    ]


def analysis_id(command: AnalysisCommand) -> str:
    safe = command.command_id.replace("-", "_").replace(".", "_")
    return f"ccv_live_{safe}_{command_run_stamp(command)}"


def command_run_stamp(command: AnalysisCommand) -> str:
    return RUN_STAMP_OVERRIDES.get(command.command_id, RUN_STAMP)


def dy_r_command(command: AnalysisCommand) -> str:
    rendered = render_catalog_dy_command(
        command,
        jobs=JOBS,
        dry_run=False,
        warmup=False,
    )
    if rendered.startswith("bin/day_run "):
        return "dy-r " + rendered[len("bin/day_run ") :]
    if rendered.startswith("dy-r "):
        return rendered
    raise RuntimeError(f"Refusing non-dy-r catalog command for {command.command_id}: {rendered}")


def command_owner(command: AnalysisCommand, index: int) -> str:
    if command.command_id == "illumina_run_qc":
        return "Agent 13"
    if command.command_id == "ont_run_qc":
        return "Agent 14"
    if command.command_id == "ultima_run_qc":
        return "Agent 15"
    return f"Agent {index:02d}"


def dayoa_runtime_tmp_patch_command() -> str:
    script = """
from pathlib import Path

common_old = '''def _normalize_run_context_row(row):
    normalized = {column: str(row.get(column, "") or "").strip() for column in RUN_CONTEXT_REQUIRED_COLUMNS}'''
common_new = '''def _normalize_run_context_row(row):
    normalized = {str(column): str(value or "").strip() for column, value in row.items()}
    for column in RUN_CONTEXT_REQUIRED_COLUMNS:
        normalized[column] = str(row.get(column, "") or "").strip()'''
ug_metrics_old = '''RUNQC_UG_DEMUX_MULTIQC_HTML = RUNQC_UG_ROOT + "/ultima_demux_fastq.multiqc.html"
RUNQC_UG_REPORT_INPUTS = [RUNQC_UG_LOG_DIR + "/ultima_run_qc_report.done"]'''
ug_metrics_new = '''RUNQC_UG_DEMUX_MULTIQC_HTML = RUNQC_UG_ROOT + "/ultima_demux_fastq.multiqc.html"
RUNQC_UG_METRICS_PATH = (
    RUNQC_UG_CONTEXT.get("METRICS_PATH", "")
    if RUNQC_UG_CONTEXT is not None
    else _runqc_text(RUNQC_UG_CFG, "metrics_path")
)
RUNQC_UG_REPORT_INPUTS = [RUNQC_UG_LOG_DIR + "/ultima_run_qc_report.done"]'''
ug_param_old = '''    params:
        metrics_path=_runqc_text(RUNQC_UG_CFG, "metrics_path"),
        run_s3_uri=RUNQC_UG_RUN_S3_URI,'''
ug_param_new = '''    params:
        metrics_path=RUNQC_UG_METRICS_PATH,
        run_s3_uri=RUNQC_UG_RUN_S3_URI,'''

edits = {
    "bin/day_run": [
        (
            "export TMPDIR=$(yq -r '.daylily.sentieon_tmpdir' \\"$CONFIG_FILE\\")",
            "export TMPDIR=\\"${DAYOA_RUNTIME_TMPDIR:-$(yq -r '.daylily.sentieon_tmpdir' \\"$CONFIG_FILE\\")}\\"",
        ),
    ],
    "bin/day_activate": [
        (
            "    export TMPDIR=$SENTIEON_TMPDIR",
            "    export TMPDIR=\\"${DAYOA_RUNTIME_TMPDIR:-$SENTIEON_TMPDIR}\\"",
        ),
    ],
    "workflow/rules/common.smk": [
        (common_old, common_new),
    ],
    "workflow/rules/run_qc_reports.smk": [
        (ug_metrics_old, ug_metrics_new),
        (ug_param_old, ug_param_new),
    ],
}
changed = []
for name, replacements in edits.items():
    path = Path(name)
    if not path.is_file():
        raise SystemExit(f"[DYEC] missing DayOA launch script: {name}")
    text = path.read_text()
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            changed.append(name)
        elif new not in text:
            raise SystemExit(f"[DYEC] expected TMPDIR assignment not found in {name}")
    path.write_text(text)
print("[DYEC] DayOA runtime TMPDIR override patch:", ",".join(sorted(set(changed))) or "already-applied")
""".strip()
    return "python3 -c " + shlex.quote(script)


def wrapped_dy_command(command: AnalysisCommand, index: int) -> str:
    aid = analysis_id(command)
    owner = command_owner(command, index)
    tmux_session = aid
    root_expr = '$(dirname "$DAYLILY_REPO_PATH")'
    lock_intent = f"DYEC catalog {command.command_id} live run on {CLUSTER}"
    run_stamp = command_run_stamp(command)
    agent_id = f"dyec-{CLUSTER}-{owner.lower().replace(' ', '')}-{run_stamp}"
    tmp_root = f"/tmp/dayoa-conda-tmp-{aid}"
    exports = [
        f"export DAYOA_AGENT_ID={shlex.quote(agent_id)}",
        "export DAYOA_AGENT_KIND=dyec-cli",
        "export DAYOA_HUMAN_REQUESTOR=jmajor",
        f"export DAYOA_TMUX_SESSION={shlex.quote(tmux_session)}",
        f"export DAYOA_LEDGER_PATH={shlex.quote(LEDGER_PATH)}",
        f"export DAYOA_RUNTIME_TMPDIR={shlex.quote(tmp_root)}",
        'mkdir -p "$DAYOA_RUNTIME_TMPDIR" "$DAYOA_RUNTIME_TMPDIR/pip-cache" "$DAYOA_RUNTIME_TMPDIR/xdg-cache" "$DAYOA_RUNTIME_TMPDIR/pip-build-tracker"',
        'export TMPDIR="$DAYOA_RUNTIME_TMPDIR"',
        'export TEMP="$DAYOA_RUNTIME_TMPDIR"',
        'export TMP="$DAYOA_RUNTIME_TMPDIR"',
        'export PIP_CACHE_DIR="$DAYOA_RUNTIME_TMPDIR/pip-cache"',
        'export XDG_CACHE_HOME="$DAYOA_RUNTIME_TMPDIR/xdg-cache"',
        'export PIP_BUILD_TRACKER="$DAYOA_RUNTIME_TMPDIR/pip-build-tracker"',
        f"analysis_root={root_expr}",
        (
            "dyec analysis visit "
            '--analysis-root "$analysis_root" '
            "--mode write "
            f"--intent {shlex.quote(lock_intent)} "
            "--human-requestor jmajor"
        ),
        (
            "dyec analysis lock acquire "
            '--analysis-root "$analysis_root" '
            "--operation write "
            f"--intent {shlex.quote(lock_intent)} "
            "--human-requestor jmajor "
            f"--command-summary {shlex.quote(command.command_id)}"
        ),
        dayoa_runtime_tmp_patch_command(),
        dy_r_command(command),
        "workflow_rc=$?",
        (
            "dyec analysis lock release "
            '--analysis-root "$analysis_root" '
            "--human-requestor jmajor "
            '--note "workflow exit $workflow_rc"'
        ),
        "exit $workflow_rc",
    ]
    return "; ".join(exports)


def write_selected() -> None:
    rows = []
    for index, command in enumerate(selected_commands(), start=1):
        rows.append(
            {
                "index": index,
                "owner": command_owner(command, index),
                "command_id": command.command_id,
                "type": command.type,
                "command_class": command.command_class,
                "input_contract": command.input_contract,
                "test_data_profile": command.test_data_profile,
                "genome": command.genome,
                "git_tag": command.git_tag,
                "requires_run_mount": command.requires_run_mount,
                "analysis_id": analysis_id(command),
                "session_name": analysis_id(command),
                "dy_r_command": dy_r_command(command),
                "wrapped_dy_command": wrapped_dy_command(command, index),
                "export_destination_s3_uri": (
                    f"{EVIDENCE_ROOT}{EXECUTING_ENTITY}/{analysis_id(command)}/"
                ),
            }
        )
    SELECTED_JSON.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tsv_path = SELECTED_JSON.with_suffix(".tsv")
    with tsv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(SELECTED_JSON)
    print(tsv_path)
    print(f"selected={len(rows)}")


def headnode_check() -> None:
    script = "\n".join(
        [
            "set -euo pipefail",
            "whoami",
            'printf "PATH=%s\\n" "$PATH"',
            "command -v dyec",
            "dyec version",
            "dyec analysis --help >/tmp/dyec_analysis_help.txt",
            "echo dyec_analysis_ok",
            "command -v day-clone",
            "command -v tmux",
            "command -v squeue",
            'grep -n "default_ref: 10.0.70" /home/ubuntu/.config/daylily/daylily_pipeline_command_catalog.yaml',
            'grep -n "git_tag: 10.0.70" /home/ubuntu/.config/daylily/daylily_pipeline_command_catalog.yaml | head -5',
            "df -h /fsx",
            'squeue -o "%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j"',
            "test -d /fsx/references/genomic_data/organism_reads_slim",
            "test -d /fsx/control_data/genomic_data/organism_reads_slim",
            "ls -ld /fsx/control_data/run_data /fsx/control_data/run_data/* 2>/dev/null || true",
            "ls -ld /fsx/run_dir_mounts /fsx/run_dir_mounts/* 2>/dev/null || true",
        ]
    )
    try:
        result = run_shell(
            HEADNODE_INSTANCE_ID,
            REGION,
            script,
            profile=PROFILE,
            timeout=240,
            comment="jul8itelx4 gate0 headnode checks",
        )
    except SsmCommandFailedError as exc:
        print(f"status={exc.result.status} rc={exc.result.response_code}")
        print("--- stdout ---")
        print(exc.result.stdout)
        print("--- stderr ---")
        print(exc.result.stderr)
        raise SystemExit(exc.result.response_code) from exc
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)


def headnode_toolchain_check() -> None:
    script = r"""
set -euo pipefail
whoami
hostname
printf 'PATH=%s\n' "$PATH"
if command -v conda >/dev/null 2>&1; then
  conda env list
fi
if [ -f /home/ubuntu/miniconda3/etc/profile.d/conda.sh ]; then
  source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
  conda activate DAYOA || true
fi
printf 'DAYOA_PATH=%s\n' "$PATH"
command -v node || true
node --version || true
command -v npm || true
npm --version || true
npm prefix -g || true
if command -v mmdc >/dev/null 2>&1; then
  printf 'mmdc_path=%s\n' "$(command -v mmdc)"
  mmdc --version || true
else
  echo mmdc_missing
fi
find /home/ubuntu/miniconda3/envs/DAYOA \( -name mmdc -o -name cli.js \) -print | head -50 || true
find /home/ubuntu/.npm /home/ubuntu/.cache -path '*mermaid*' -print | head -50 || true
find /home/ubuntu/miniconda3/pkgs -maxdepth 1 -name '*.conda' -size 0 -print | head -50 || true
"""
    try:
        result = run_shell(
            HEADNODE_INSTANCE_ID,
            REGION,
            script,
            profile=PROFILE,
            timeout=240,
            comment="jul8itelx4 inspect DayOA toolchain",
        )
    except SsmCommandFailedError as exc:
        print(f"status={exc.result.status} rc={exc.result.response_code}")
        print("--- stdout ---")
        print(exc.result.stdout)
        print("--- stderr ---")
        print(exc.result.stderr)
        raise SystemExit(exc.result.response_code) from exc
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)


def headnode_toolchain_repair() -> None:
    script = r"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda clean --tarballs --packages -y
conda activate DAYOA
rm -rf "$CONDA_PREFIX/lib/node_modules/@mermaid-js/mermaid-cli"
rm -f "$CONDA_PREFIX/bin/mmdc"
rm -rf /home/ubuntu/.cache/puppeteer/chrome/linux-148.0.7778.97
npm install -g @mermaid-js/mermaid-cli@11.15.0
if ! command -v mmdc >/dev/null 2>&1; then
  prefix="$(npm prefix -g)"
  if [ -x "$prefix/bin/mmdc" ]; then
    mkdir -p /home/ubuntu/.local/bin
    ln -sfn "$prefix/bin/mmdc" /home/ubuntu/.local/bin/mmdc
    export PATH="/home/ubuntu/.local/bin:$PATH"
  elif [ -f "$prefix/lib/node_modules/@mermaid-js/mermaid-cli/src/cli.js" ]; then
    mkdir -p /home/ubuntu/.local/bin
    cat > /home/ubuntu/.local/bin/mmdc <<'SH'
#!/usr/bin/env bash
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate DAYOA
exec node "$CONDA_PREFIX/lib/node_modules/@mermaid-js/mermaid-cli/src/cli.js" "$@"
SH
    chmod 755 /home/ubuntu/.local/bin/mmdc
    export PATH="/home/ubuntu/.local/bin:$PATH"
  fi
fi
printf 'mmdc_path=%s\n' "$(command -v mmdc)"
mmdc --version
"""
    try:
        result = run_shell(
            HEADNODE_INSTANCE_ID,
            REGION,
            script,
            profile=PROFILE,
            timeout=1200,
            comment="jul8itelx4 repair DayOA mmdc and conda cache",
        )
    except SsmCommandFailedError as exc:
        print(f"status={exc.result.status} rc={exc.result.response_code}")
        print("--- stdout ---")
        print(exc.result.stdout)
        print("--- stderr ---")
        print(exc.result.stderr)
        raise SystemExit(exc.result.response_code) from exc
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)


def prepare_sample_configs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_repository_catalog(CATALOG_PATH)
    role_uris = catalog_role_uris(catalog)
    stage_s3_uri = f"{EVIDENCE_ROOT}_config_generation/"
    for command in selected_commands():
        if command.input_contract != "sample_manifest":
            continue
        command_dir = OUTPUT_DIR / command.command_id
        command_dir.mkdir(parents=True, exist_ok=True)
        manifest = write_sample_manifest(command, command_dir)
        config_dir = command_dir / "config"
        if config_dir.exists():
            for pattern in ("*_samples.tsv", "*_units.tsv"):
                for generated in config_dir.glob(pattern):
                    generated.unlink()
        argv = [
            str(manifest),
            "--config-only",
            "--config-dir",
            str(config_dir),
            "--reference-s3-uri",
            role_uris["reference_s3_uri"],
            "--control-data-s3-uri",
            role_uris["control_data_s3_uri"],
            "--stage-s3-uri",
            stage_s3_uri,
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ]
        rc = default_stage_func(argv)
        if rc != 0:
            raise RuntimeError(f"Config generation failed for {command.command_id}: rc={rc}")
        samples, units = generated_config_paths(config_dir)
        receipt = {
            "command_id": command.command_id,
            "analysis_id": analysis_id(command),
            "manifest": str(manifest),
            "samples": str(samples),
            "units": str(units),
        }
        (command_dir / "config_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, sort_keys=True))


def available_run_mounts() -> dict[str, object]:
    records = list_run_mounts(
        cluster_name=CLUSTER,
        fsx_file_system_id=None,
        region=REGION,
        profile=PROFILE,
        purpose=MOUNT_PURPOSE_RUN,
    )
    return {
        normalize_s3_uri(record.source_s3_uri): record
        for record in records
        if str(record.lifecycle).upper() == "AVAILABLE"
    }


def prepare_run_contexts(command_id: str = "") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_repository_catalog(CATALOG_PATH)
    run_mounts = available_run_mounts()
    for command in selected_commands():
        if command.input_contract != "run_context":
            continue
        if command_id and command.command_id != command_id:
            continue
        source = run_profile_source(command, catalog)
        record = run_mounts.get(source)
        if record is None:
            raise RuntimeError(
                f"No AVAILABLE run DRA for {command.command_id}: {source}. "
                "Wait for dyec mounts list to report AVAILABLE and verify before launch."
            )
        command_dir = OUTPUT_DIR / command.command_id
        run_context = command_dir / "runs.tsv"
        write_run_context(
            run_context,
            command=command,
            record=record,
            test_data_profile=catalog.test_data_profiles[command.test_data_profile],
            profile=PROFILE,
            region=REGION,
        )
        receipt = {
            "command_id": command.command_id,
            "analysis_id": analysis_id(command),
            "run_context": str(run_context),
            "mount_id": record.mount_id,
            "association_id": record.association_id,
            "source_s3_uri": record.source_s3_uri,
            "headnode_path": record.headnode_path,
            "lifecycle": record.lifecycle,
        }
        (command_dir / "run_context_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, sort_keys=True))


def slurm_job_count() -> int:
    result = subprocess.run(
        [
            "dyec",
            "headnode",
            "jobs",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    rows = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("DAY-EC activated.") or line.startswith("JOBID"):
            continue
        rows.append(line)
    return len(rows)


def workflow_status(command: AnalysisCommand) -> dict[str, object] | None:
    result = subprocess.run(
        [
            "dyec",
            "workflow",
            "status",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            analysis_id(command),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    text = result.stdout
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return json.loads(text[start : end + 1])


def workflow_log_has_submission(command: AnalysisCommand) -> bool:
    result = subprocess.run(
        [
            "dyec",
            "workflow",
            "logs",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            analysis_id(command),
            "--lines",
            "240",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    lowered = result.stdout.lower()
    return "submitted job" in lowered or "submitted batch job" in lowered


def workflow_log_has_success(command: AnalysisCommand) -> bool:
    result = subprocess.run(
        [
            "dyec",
            "workflow",
            "logs",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            analysis_id(command),
            "--lines",
            "260",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    lowered = result.stdout.lower()
    return "workflow success" in lowered and "return code: 0" in lowered


def wait_for_submission(command: AnalysisCommand, *, baseline_jobs: int) -> None:
    deadline = time.time() + 900
    while time.time() < deadline:
        current_jobs = slurm_job_count()
        if current_jobs > baseline_jobs:
            print(
                json.dumps(
                    {
                        "command_id": command.command_id,
                        "analysis_id": analysis_id(command),
                        "submission_gate": "slurm_job_count_increased",
                        "baseline_jobs": baseline_jobs,
                        "current_jobs": current_jobs,
                    },
                    sort_keys=True,
                )
            )
            return
        if workflow_log_has_submission(command):
            print(
                json.dumps(
                    {
                        "command_id": command.command_id,
                        "analysis_id": analysis_id(command),
                        "submission_gate": "workflow_log_submission",
                        "baseline_jobs": baseline_jobs,
                        "current_jobs": current_jobs,
                    },
                    sort_keys=True,
                )
            )
            return
        status = workflow_status(command)
        if status is not None and status.get("exit_code") is not None:
            if workflow_log_has_success(command):
                print(
                    json.dumps(
                        {
                            "command_id": command.command_id,
                            "analysis_id": analysis_id(command),
                            "submission_gate": "workflow_success_before_slurm_submission",
                            "baseline_jobs": baseline_jobs,
                            "current_jobs": current_jobs,
                            "status_exit_code": status.get("exit_code"),
                        },
                        sort_keys=True,
                    )
                )
                return
            raise RuntimeError(
                f"{command.command_id} reached terminal status before Slurm submission: "
                f"{json.dumps(status, sort_keys=True)}"
            )
        time.sleep(20)
    raise TimeoutError(f"Timed out waiting for Slurm submission from {command.command_id}.")


def launch_sample_commands(command_id: str = "") -> None:
    write_selected()
    for index, command in enumerate(selected_commands(), start=1):
        if command.input_contract != "sample_manifest":
            continue
        if command_id and command.command_id != command_id:
            continue
        aid = analysis_id(command)
        command_dir = OUTPUT_DIR / command.command_id
        samples, units = generated_config_paths(command_dir / "config")
        argv = [
            "dyec",
            "workflow",
            "launch",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--analysis-id",
            aid,
            "--executing-entity",
            EXECUTING_ENTITY,
            "--repository",
            command.repository,
            "--git-tag",
            DAYOA_TAG,
            "--genome",
            command.genome,
            "--dy-command",
            wrapped_dy_command(command, index),
            "--samples-file",
            str(samples),
            "--units-file",
            str(units),
            "--session-name",
            aid,
            "--project",
            CLUSTER,
            "--skip-project-check",
        ]
        print("LAUNCH", command.command_id, aid)
        print(json.dumps(argv))
        baseline_jobs = slurm_job_count()
        result = subprocess.run(argv, cwd=REPO_ROOT, text=True, capture_output=True)
        launch_dir = command_dir / "launch"
        launch_dir.mkdir(parents=True, exist_ok=True)
        (launch_dir / "argv.json").write_text(json.dumps(argv, indent=2) + "\n", encoding="utf-8")
        (launch_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (launch_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        (launch_dir / "returncode.txt").write_text(f"{result.returncode}\n", encoding="utf-8")
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        wait_for_submission(command, baseline_jobs=baseline_jobs)


def launch_run_qc_commands(command_id: str = "") -> None:
    write_selected()
    prepare_run_contexts(command_id=command_id)
    for index, command in enumerate(selected_commands(), start=1):
        if command.input_contract != "run_context":
            continue
        if command_id and command.command_id != command_id:
            continue
        aid = analysis_id(command)
        command_dir = OUTPUT_DIR / command.command_id
        run_context = command_dir / "runs.tsv"
        if not run_context.is_file():
            raise RuntimeError(f"Run context not found for {command.command_id}: {run_context}")
        argv = [
            "dyec",
            "workflow",
            "launch",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--analysis-id",
            aid,
            "--executing-entity",
            EXECUTING_ENTITY,
            "--repository",
            command.repository,
            "--git-tag",
            DAYOA_TAG,
            "--genome",
            command.genome,
            "--dy-command",
            wrapped_dy_command(command, index),
            "--run-context-file",
            str(run_context),
            "--session-name",
            aid,
            "--project",
            CLUSTER,
            "--skip-project-check",
        ]
        print("LAUNCH", command.command_id, aid)
        print(json.dumps(argv))
        baseline_jobs = slurm_job_count()
        result = subprocess.run(argv, cwd=REPO_ROOT, text=True, capture_output=True)
        launch_dir = command_dir / "launch"
        launch_dir.mkdir(parents=True, exist_ok=True)
        (launch_dir / "argv.json").write_text(json.dumps(argv, indent=2) + "\n", encoding="utf-8")
        (launch_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (launch_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        (launch_dir / "returncode.txt").write_text(f"{result.returncode}\n", encoding="utf-8")
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        wait_for_submission(command, baseline_jobs=baseline_jobs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "write-selected",
            "headnode-check",
            "headnode-toolchain-check",
            "headnode-toolchain-repair",
            "prepare-sample-configs",
            "launch-sample-commands",
            "prepare-run-contexts",
            "launch-run-qc-commands",
        ],
    )
    parser.add_argument("--command-id", default="")
    args = parser.parse_args()
    if args.command == "write-selected":
        write_selected()
    elif args.command == "headnode-check":
        headnode_check()
    elif args.command == "headnode-toolchain-check":
        headnode_toolchain_check()
    elif args.command == "headnode-toolchain-repair":
        headnode_toolchain_repair()
    elif args.command == "prepare-sample-configs":
        prepare_sample_configs()
    elif args.command == "launch-sample-commands":
        launch_sample_commands(command_id=args.command_id)
    elif args.command == "prepare-run-contexts":
        prepare_run_contexts(command_id=args.command_id)
    elif args.command == "launch-run-qc-commands":
        launch_run_qc_commands(command_id=args.command_id)


if __name__ == "__main__":
    main()
