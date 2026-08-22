"""DRA-only export of cluster-scoped DayOA runtime caches."""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import shlex
from pathlib import Path
from typing import Any

import yaml

from daylily_ec.analysis_identity import validate_analysis_segment
from daylily_ec.aws.ssm import SsmCommandFailedError

RUNTIME_CACHE_EXPORT_SCHEMA_VERSION = 1
RUNTIME_CACHE_STAGE_MARKER = "DYEC_RUNTIME_CACHE_STAGE_RESULT"
RUNTIME_CACHE_RECEIPT = "runtime_cache_export.yaml"
SUPPORTED_CACHE_USERS = {"ubuntu", "daylily", "ec2-user"}


class RuntimeCacheExportError(RuntimeError):
    """Raised when a runtime-cache export cannot satisfy its immutable contract."""


@dataclasses.dataclass(frozen=True)
class RuntimeCacheExportOptions:
    cluster_name: str
    executing_entity: str
    cache_export_id: str
    destination_s3_uri: str
    region: str
    profile: str | None
    output_dir: Path
    human_requestor: str
    cache_user: str = "ubuntu"
    stage_timeout_seconds: int = 7200
    export_timeout_seconds: int = 5400
    dry_run: bool = False

    @property
    def stage_root(self) -> str:
        return runtime_cache_stage_root(
            executing_entity=self.executing_entity,
            cache_export_id=self.cache_export_id,
        )


def runtime_cache_stage_root(*, executing_entity: str, cache_export_id: str) -> str:
    """Return the one valid DRA-eligible staging root for a cache export."""

    entity = validate_analysis_segment(executing_entity, field_name="executing_entity")
    export_id = validate_analysis_segment(cache_export_id, field_name="cache_export_id")
    return f"/fsx/analysis_results/{entity}/{export_id}"


def validate_runtime_cache_options(options: RuntimeCacheExportOptions) -> None:
    """Validate all local command inputs without discovering alternates."""

    validate_analysis_segment(options.cluster_name, field_name="cluster_name")
    runtime_cache_stage_root(
        executing_entity=options.executing_entity,
        cache_export_id=options.cache_export_id,
    )
    if options.cache_user not in SUPPORTED_CACHE_USERS:
        raise RuntimeCacheExportError(
            "cache_user must be one of: " + ", ".join(sorted(SUPPORTED_CACHE_USERS))
        )
    if not options.human_requestor.strip():
        raise RuntimeCacheExportError("human_requestor must not be blank.")
    if options.stage_timeout_seconds <= 0:
        raise RuntimeCacheExportError("stage_timeout_seconds must be greater than zero.")
    if options.export_timeout_seconds < 2400:
        raise RuntimeCacheExportError(
            "export_timeout_seconds must be at least 2400 seconds for FSx DRA operations."
        )

    from daylily_ec.workflow.export_data import (
        ExportError,
        validate_export_destination_s3_uri,
    )

    try:
        validate_export_destination_s3_uri(
            options.destination_s3_uri,
            source_path=options.stage_root,
            cluster_name=options.cluster_name,
        )
    except (ExportError, ValueError) as exc:
        raise RuntimeCacheExportError(str(exc)) from exc


def _q(value: str) -> str:
    return shlex.quote(str(value))


def build_runtime_cache_stage_script(options: RuntimeCacheExportOptions) -> str:
    """Build the fail-closed Ubuntu headnode staging script.

    The script intentionally contains no S3 transfer command. Its only data
    movement is ``cp -a`` from the generation-scoped writable cache into the
    new analysis root. The caller performs the subsequent export with FSx DRA
    APIs through :mod:`daylily_ec.workflow.export_data`.
    """

    validate_runtime_cache_options(options)
    agent_id = f"dyec-runtime-cache-{options.cache_export_id}"
    intent = f"stage runtime caches for DRA export {options.cache_export_id}"
    return f"""set -Eeuo pipefail
umask 077

analysis_root={_q(options.stage_root)}
cache_user={_q(options.cache_user)}
lock_acquired=0

export DAYOA_AGENT_ID={_q(agent_id)}
export DAYOA_AGENT_KIND=dyec
export DAYOA_HUMAN_REQUESTOR={_q(options.human_requestor)}
export DAYOA_TMUX_SESSION={_q(agent_id)}

finish() {{
  rc="$?"
  trap - EXIT HUP INT TERM
  if [[ "${{lock_acquired}}" == "1" ]]; then
    if ! dyec analysis lock release \
      --analysis-root "${{analysis_root}}" \
      --note "runtime-cache staging exited rc=${{rc}}" >/dev/null; then
      echo "ERROR: unable to release runtime-cache staging lock: ${{analysis_root}}" >&2
      if [[ "${{rc}}" == "0" ]]; then
        rc=34
      fi
    fi
  fi
  exit "${{rc}}"
}}
trap finish EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

command -v cp >/dev/null
command -v dyec >/dev/null
command -v find >/dev/null
command -v pgrep >/dev/null
test -r /etc/profile.d/daylily-cluster-cache-namespace.sh
source /etc/profile.d/daylily-cluster-cache-namespace.sh
test -n "${{DAYOA_CLUSTER_CACHE_NAMESPACE:-}}"
[[ "${{DAYOA_CLUSTER_CACHE_NAMESPACE}}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]

source_conda="/fsx/resources/environments/conda/${{cache_user}}/${{DAYOA_CLUSTER_CACHE_NAMESPACE}}"
source_containers="/fsx/resources/environments/containers/${{cache_user}}/${{DAYOA_CLUSTER_CACHE_NAMESPACE}}"
stage_conda="${{analysis_root}}/cached_envs/conda"
stage_containers="${{analysis_root}}/cached_envs/containers"
metadata_dir="${{analysis_root}}/.dyec_runtime_cache"
manifest="${{analysis_root}}/runtime_cache_manifest.tsv"

test -d /fsx/analysis_results
if [[ -e "${{analysis_root}}" ]]; then
  echo "ERROR: runtime-cache staging root already exists: ${{analysis_root}}" >&2
  exit 20
fi
test -d "${{source_conda}}"
test -d "${{source_containers}}"

active_cache_mutators() {{
  pgrep -u "${{cache_user}}" -af '(^|[ /])(conda|mamba|micromamba)([ ]+)(create|install|update)([ ]|$)|(^|[ /])(apptainer|singularity)([ ]+)(pull|build)([ ]|$)|(^|[ /])(snakemake|nextflow)([ ]|$)' || true
}}

cache_activity="$(active_cache_mutators)"
if [[ -n "${{cache_activity}}" ]]; then
  echo "ERROR: an active workflow or runtime-cache builder makes the cache mutable:" >&2
  printf '%s\n' "${{cache_activity}}" >&2
  exit 21
fi

dyec analysis lock acquire \
  --analysis-root "${{analysis_root}}" \
  --operation write \
  --intent {_q(intent)} \
  --command-summary "cp -a completed runtime caches into a fresh DRA export root" >/dev/null
lock_acquired=1

mkdir -p "${{stage_conda}}" "${{stage_containers}}" "${{metadata_dir}}/links"
printf 'kind\tname\tsource\tstage\tbytes\tsymlinks\n' > "${{manifest}}"
find "${{source_conda}}" "${{source_containers}}" -xdev \
  -printf '%p\t%y\t%s\t%T@\t%l\n' | LC_ALL=C sort > "${{metadata_dir}}/source.before.tsv"

declare -a conda_dirs=()
declare -a container_files=()
seeded_container_links=0
shopt -s nullglob dotglob

for entry in "${{source_conda}}"/*; do
  name="$(basename -- "${{entry}}")"
  [[ "${{name}}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {{
    echo "ERROR: unsafe Conda cache entry name: ${{name}}" >&2
    exit 22
  }}
  if [[ -L "${{entry}}" ]]; then
    echo "ERROR: top-level linked Conda cache entries are forbidden: ${{entry}}" >&2
    exit 23
  elif [[ -d "${{entry}}" ]]; then
    test -f "${{entry}}/conda-meta/history" || {{
      echo "ERROR: incomplete Conda environment missing conda-meta/history: ${{entry}}" >&2
      exit 24
    }}
    test -f "${{entry}}.yaml" && test ! -L "${{entry}}.yaml" || {{
      echo "ERROR: completed Conda environment lacks a real adjacent YAML: ${{entry}}" >&2
      exit 25
    }}
    conda_dirs+=("${{entry}}")
  elif [[ -f "${{entry}}" && "${{entry}}" == *.yaml ]]; then
    base="${{entry%.yaml}}"
    test -d "${{base}}" && test ! -L "${{base}}" || {{
      echo "ERROR: orphan Conda environment YAML: ${{entry}}" >&2
      exit 26
    }}
  else
    echo "ERROR: unsupported Conda cache entry: ${{entry}}" >&2
    exit 27
  fi
done

for entry in "${{source_containers}}"/*; do
  name="$(basename -- "${{entry}}")"
  [[ "${{name}}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {{
    echo "ERROR: unsafe container cache entry name: ${{name}}" >&2
    exit 28
  }}
  if [[ -L "${{entry}}" ]]; then
    seeded_container_links=$((seeded_container_links + 1))
  elif [[ -f "${{entry}}" && ( "${{name}}" == *.sif || "${{name}}" == *.simg ) && -s "${{entry}}" ]]; then
    container_files+=("${{entry}}")
  else
    echo "ERROR: unsupported or incomplete real container cache entry: ${{entry}}" >&2
    exit 29
  fi
done

if [[ "${{#conda_dirs[@]}}" -eq 0 && "${{#container_files[@]}}" -eq 0 ]]; then
  echo "ERROR: no complete real runtime-cache entries were found" >&2
  exit 30
fi

conda_count=0
container_count=0
total_symlinks=0

for source_dir in "${{conda_dirs[@]}}"; do
  name="$(basename -- "${{source_dir}}")"
  destination_dir="${{stage_conda}}/${{name}}"
  source_bytes="$(du -sb -- "${{source_dir}}" | cut -f1)"
  find "${{source_dir}}" -type l -printf '%P\t%l\n' | LC_ALL=C sort > "${{metadata_dir}}/links/${{name}}.source.tsv"
  cp -a -- "${{source_dir}}" "${{destination_dir}}"
  cp -a -- "${{source_dir}}.yaml" "${{stage_conda}}/${{name}}.yaml"
  test -f "${{destination_dir}}/conda-meta/history"
  cmp -s -- "${{source_dir}}.yaml" "${{stage_conda}}/${{name}}.yaml"
  destination_bytes="$(du -sb -- "${{destination_dir}}" | cut -f1)"
  [[ "${{source_bytes}}" == "${{destination_bytes}}" ]] || {{
    echo "ERROR: staged Conda byte count differs for ${{name}}" >&2
    exit 31
  }}
  find "${{destination_dir}}" -type l -printf '%P\t%l\n' | LC_ALL=C sort > "${{metadata_dir}}/links/${{name}}.stage.tsv"
  cmp -s -- "${{metadata_dir}}/links/${{name}}.source.tsv" "${{metadata_dir}}/links/${{name}}.stage.tsv" || {{
    echo "ERROR: staged Conda symlink manifest differs for ${{name}}" >&2
    exit 32
  }}
  link_count="$(wc -l < "${{metadata_dir}}/links/${{name}}.source.tsv")"
  total_symlinks=$((total_symlinks + link_count))
  printf 'conda\t%s\t%s\t%s\t%s\t%s\n' \
    "${{name}}" "${{source_dir}}" "${{destination_dir}}" "${{source_bytes}}" "${{link_count}}" >> "${{manifest}}"
  conda_count=$((conda_count + 1))
done

for source_file in "${{container_files[@]}}"; do
  name="$(basename -- "${{source_file}}")"
  destination_file="${{stage_containers}}/${{name}}"
  cp -a -- "${{source_file}}" "${{destination_file}}"
  cmp -s -- "${{source_file}}" "${{destination_file}}"
  file_bytes="$(stat -c %s -- "${{destination_file}}")"
  printf 'container\t%s\t%s\t%s\t%s\t0\n' \
    "${{name}}" "${{source_file}}" "${{destination_file}}" "${{file_bytes}}" >> "${{manifest}}"
  container_count=$((container_count + 1))
done

cache_activity="$(active_cache_mutators)"
if [[ -n "${{cache_activity}}" ]]; then
  echo "ERROR: a workflow or cache builder started during staging; refusing DRA export" >&2
  printf '%s\n' "${{cache_activity}}" >&2
  exit 33
fi
find "${{source_conda}}" "${{source_containers}}" -xdev \
  -printf '%p\t%y\t%s\t%T@\t%l\n' | LC_ALL=C sort > "${{metadata_dir}}/source.after.tsv"
cmp -s -- "${{metadata_dir}}/source.before.tsv" "${{metadata_dir}}/source.after.tsv" || {{
  echo "ERROR: runtime-cache source inventory changed during staging" >&2
  exit 35
}}

printf '%s\n' "${{DAYOA_CLUSTER_CACHE_NAMESPACE}}" > "${{metadata_dir}}/source_namespace"
printf '%s\n' "${{seeded_container_links}}" > "${{metadata_dir}}/skipped_seeded_container_links"
dyec analysis lock release \
  --analysis-root "${{analysis_root}}" \
  --note "runtime-cache cp -a staging complete; ready for no-delete DRA export" >/dev/null
lock_acquired=0
dyec analysis visit \
  --analysis-root "${{analysis_root}}" \
  --mode export \
  --intent "export staged runtime cache only through FSx DRA" \
  --note "AWS S3 CLI object transfer is forbidden" >/dev/null

printf '{RUNTIME_CACHE_STAGE_MARKER}\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "${{DAYOA_CLUSTER_CACHE_NAMESPACE}}" "${{conda_count}}" "${{container_count}}" \
  "${{total_symlinks}}" "${{seeded_container_links}}" "${{manifest}}"
"""


def parse_runtime_cache_stage_result(stdout: str) -> dict[str, Any]:
    """Parse the single terminal marker emitted after lock release and visit logging."""

    matches = [
        line
        for line in str(stdout or "").splitlines()
        if line.startswith(f"{RUNTIME_CACHE_STAGE_MARKER}\t")
    ]
    if len(matches) != 1:
        raise RuntimeCacheExportError(
            "runtime-cache staging did not emit exactly one terminal result marker."
        )
    fields = matches[0].split("\t")
    if len(fields) != 7:
        raise RuntimeCacheExportError("runtime-cache staging result marker is malformed.")
    try:
        conda_count = int(fields[2])
        container_count = int(fields[3])
        symlink_count = int(fields[4])
        skipped_seeded_container_links = int(fields[5])
    except ValueError as exc:
        raise RuntimeCacheExportError(
            "runtime-cache staging result contains a non-integer count."
        ) from exc
    if (
        min(
            conda_count,
            container_count,
            symlink_count,
            skipped_seeded_container_links,
        )
        < 0
    ):
        raise RuntimeCacheExportError("runtime-cache staging result contains a negative count.")
    if conda_count + container_count == 0:
        raise RuntimeCacheExportError("runtime-cache staging result contains no copied entries.")
    return {
        "cluster_cache_namespace": fields[1],
        "conda_environment_count": conda_count,
        "container_image_count": container_count,
        "preserved_conda_symlink_count": symlink_count,
        "skipped_seeded_container_link_count": skipped_seeded_container_links,
        "manifest_path": fields[6],
    }


def _base_receipt(options: RuntimeCacheExportOptions) -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_CACHE_EXPORT_SCHEMA_VERSION,
        "status": "planned" if options.dry_run else "started",
        "transport": "fsx_dra",
        "s3_object_copy_transport": "forbidden",
        "cluster_name": options.cluster_name,
        "region": options.region,
        "cache_user": options.cache_user,
        "executing_entity": options.executing_entity,
        "cache_export_id": options.cache_export_id,
        "stage_root": options.stage_root,
        "destination_s3_uri": options.destination_s3_uri,
        "staging_copy_command": "cp -a",
        "staged_fsx_data_deleted": False,
        "dry_run": options.dry_run,
    }


def _write_receipt(options: RuntimeCacheExportOptions, receipt: dict[str, Any]) -> None:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    (options.output_dir / RUNTIME_CACHE_RECEIPT).write_text(
        yaml.safe_dump({"runtime_cache_export": receipt}, sort_keys=False),
        encoding="utf-8",
    )


def _preflight_dra_export(options: RuntimeCacheExportOptions) -> str:
    from daylily_ec.run_mounts import describe_fsx_file_system, validate_dra_compatible_file_system
    from daylily_ec.workflow.export_data import (
        _create_session,
        resolve_export_fsx_id,
        validate_no_overlapping_export_dra,
        validate_s3_destination_prefix_empty,
    )

    session = _create_session(options.region, options.profile)
    fsx_client = session.client("fsx")
    s3_client = session.client("s3")
    fsx_file_system_id = resolve_export_fsx_id(
        fsx_client,
        cluster_name=options.cluster_name,
        fsx_file_system_id=None,
    )
    validate_dra_compatible_file_system(describe_fsx_file_system(fsx_client, fsx_file_system_id))
    validate_no_overlapping_export_dra(
        fsx_client,
        fsx_file_system_id=fsx_file_system_id,
        source_path=options.stage_root,
        destination_s3_uri=options.destination_s3_uri,
    )
    validate_s3_destination_prefix_empty(
        s3_client,
        options.destination_s3_uri,
        source_path=options.stage_root,
        cluster_name=options.cluster_name,
    )
    return fsx_file_system_id


def run_runtime_cache_export(options: RuntimeCacheExportOptions) -> dict[str, Any]:
    """Stage complete runtime caches and export them through an FSx DRA only."""

    validate_runtime_cache_options(options)
    if options.output_dir.exists():
        raise RuntimeCacheExportError(f"output_dir must not already exist: {options.output_dir}")
    receipt = _base_receipt(options)
    if options.dry_run:
        receipt["status"] = "planned"
        receipt["stage_script"] = build_runtime_cache_stage_script(options)
        return receipt

    options.output_dir.mkdir(parents=True, exist_ok=False)
    try:
        from daylily_ec.aws.ssm import (
            resolve_headnode_instance_id,
            run_shell,
            wait_for_ssm_online,
        )
        from daylily_ec.workflow.export_data import (
            RUNTIME_CACHE_EXPORT_KIND,
            STATUS_FILENAME,
            ExportOptions,
            run_export_workflow,
        )

        target = resolve_headnode_instance_id(
            options.cluster_name,
            options.region,
            profile=options.profile,
        )
        wait_for_ssm_online(
            target.instance_id,
            options.region,
            profile=options.profile,
            timeout=120,
        )
        fsx_file_system_id = _preflight_dra_export(options)
        receipt["headnode_instance_id"] = target.instance_id
        receipt["fsx_file_system_id"] = fsx_file_system_id
        stage_result = run_shell(
            target.instance_id,
            options.region,
            build_runtime_cache_stage_script(options),
            profile=options.profile,
            as_user="ubuntu",
            timeout=options.stage_timeout_seconds,
            comment=f"DYEC runtime-cache export stage {options.cache_export_id}",
        )
        receipt["ssm_command_id"] = stage_result.command_id
        receipt["stage"] = parse_runtime_cache_stage_result(stage_result.stdout)

        # Repeat both immutable-destination checks after the long cp -a stage.
        repeated_fsx_id = _preflight_dra_export(options)
        if repeated_fsx_id != fsx_file_system_id:
            raise RuntimeCacheExportError(
                "cluster FSx identity changed between runtime-cache preflight and export."
            )

        dra_output_dir = options.output_dir / "dra"
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(captured_stdout),
            contextlib.redirect_stderr(captured_stderr),
        ):
            rc = run_export_workflow(
                ExportOptions(
                    cluster_name=options.cluster_name,
                    fsx_file_system_id=fsx_file_system_id,
                    source_path=options.stage_root,
                    destination_s3_uri=options.destination_s3_uri,
                    region=options.region,
                    profile=options.profile,
                    output_dir=dra_output_dir,
                    wait=True,
                    timeout_seconds=options.export_timeout_seconds,
                    delete_data_in_file_system=False,
                    export_kind=RUNTIME_CACHE_EXPORT_KIND,
                )
            )
        export_receipt_path = dra_output_dir / STATUS_FILENAME
        if not export_receipt_path.is_file():
            raise RuntimeCacheExportError("FSx DRA export did not write fsx_export.yaml.")
        export_document = yaml.safe_load(export_receipt_path.read_text(encoding="utf-8"))
        export_receipt = (
            export_document.get("fsx_export") if isinstance(export_document, dict) else None
        )
        if not isinstance(export_receipt, dict):
            raise RuntimeCacheExportError("FSx DRA export receipt is malformed.")
        receipt["fsx_export"] = export_receipt
        if rc != 0 or export_receipt.get("status") != "success":
            detail = (
                export_receipt.get("failure_details")
                or captured_stderr.getvalue()
                or captured_stdout.getvalue()
            )
            raise RuntimeCacheExportError(f"FSx DRA export failed: {detail}")
        if export_receipt.get("detached") is not True:
            raise RuntimeCacheExportError("FSx DRA export did not detach its temporary DRA.")
        if export_receipt.get("delete_data_in_file_system") is not False:
            raise RuntimeCacheExportError("runtime-cache export must retain staged FSx data.")

        receipt["status"] = "success"
        _write_receipt(options, receipt)
        return receipt
    except SsmCommandFailedError as exc:
        receipt["status"] = "error"
        receipt["failure_details"] = {
            "message": str(exc),
            "ssm_command_id": exc.result.command_id,
            "stdout": exc.result.stdout,
            "stderr": exc.result.stderr,
        }
        _write_receipt(options, receipt)
        raise RuntimeCacheExportError(str(exc)) from exc
    except Exception as exc:
        receipt["status"] = "error"
        receipt["failure_details"] = {"message": str(exc)}
        _write_receipt(options, receipt)
        if isinstance(exc, RuntimeCacheExportError):
            raise
        raise RuntimeCacheExportError(str(exc)) from exc


def receipt_as_json(receipt: dict[str, Any]) -> str:
    """Return deterministic JSON for tests and non-Typer callers."""

    return json.dumps(receipt, indent=2, sort_keys=True)
