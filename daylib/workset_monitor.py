"""Monitor S3 workset directories and launch Daylily pipelines automatically."""

from __future__ import annotations

import concurrent.futures
import contextlib
import csv
import dataclasses
import datetime as dt
import importlib.resources as resources
import json
import logging
import os
import re
import shutil
import socket
import shlex
import subprocess
import time
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

import boto3
from botocore.exceptions import ClientError
import yaml  # type: ignore[import-untyped]

LOGGER = logging.getLogger("daylily.workset_monitor")

READY_CLUSTER_STATUSES = {"CREATE_COMPLETE", "UPDATE_COMPLETE"}
READY_COMPUTE_FLEET_STATUSES = {"RUNNING", "ENABLED", "STARTED"}

SENTINEL_FILES = {
    "ready": "daylily.ready",
    "lock": "daylily.lock",
    "in_progress": "daylily.in_progress",
    "error": "daylily.error",
    "complete": "daylily.complete",
    "ignore": "daylily.ignore",
}
OPTIONAL_SENTINELS = {
    SENTINEL_FILES["lock"],
    SENTINEL_FILES["in_progress"],
    SENTINEL_FILES["error"],
    SENTINEL_FILES["complete"],
    SENTINEL_FILES["ignore"],
}
SENTINEL_SUFFIX = tuple(
    "daylily." + suffix
    for suffix in ("ready", "lock", "in_progress", "error", "complete", "ignore")
)

DEFAULT_STAGE_SAMPLES_NAME = "stage_samples.tsv"
WORK_YAML_NAME = "daylily_work.yaml"
INFO_YAML_NAME = "daylily_info.yaml"
SAMPLE_DATA_DIRNAME = "sample_data"
PIPELINE_LOCATION_MARKER = ".daylily-monitor-location"
PIPELINE_SESSION_MARKER = ".daylily-monitor-tmux-session"
PIPELINE_START_MARKER = ".daylily-monitor-pipeline-start"
PIPELINE_SUCCESS_SENTINEL = "daylily.successful_run"
PIPELINE_FAILURE_SENTINEL = "daylily.failed_run"
FSX_EXPORT_STATUS_FILENAME = "fsx_export.yaml"
CLUSTER_STATE_DIR = "_clusters"
CLUSTER_IDLE_MARKER = "idle_since"

STATE_PRIORITIES = {
    "error": 0,
    "in-progress": 1,
    "locked": 2,
    "ready": 3,
    "complete": 4,
    "ignored": 5,
    "unknown": 6,
}
STATE_COLORS = {
    "error": "\033[31m",
    "in-progress": "\033[33m",
    "locked": "\033[36m",
    "ready": "\033[34m",
    "complete": "\033[32m",
    "ignored": "\033[90m",
    "unknown": "\033[37m",
}


class MonitorError(RuntimeError):
    """Raised when a workset fails validation or processing."""


class CommandFailedError(MonitorError):
    """Raised when an external command fails."""

    def __init__(self, command_label: str, command_display: str) -> None:
        super().__init__(f"Command failed: {command_display}")
        self.command_label = command_label
        self.command_display = command_display


@dataclasses.dataclass
class AWSConfig:
    profile: str
    region: str
    session_duration_seconds: Optional[int] = None

    def session_kwargs(self) -> Dict[str, str]:
        kwargs: Dict[str, str] = {"region_name": self.region}
        if self.profile:
            kwargs["profile_name"] = self.profile
        return kwargs


@dataclasses.dataclass
class MonitorOptions:
    bucket: str
    prefix: str
    poll_interval_seconds: int = 60
    ready_lock_backoff_seconds: int = 30
    continuous: bool = True
    sentinel_index_prefix: Optional[str] = None
    archive_prefix: Optional[str] = None

    def normalised_prefix(self) -> str:
        prefix = self.prefix.lstrip("/")
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        return prefix

    def normalised_archive_prefix(self) -> Optional[str]:
        if not self.archive_prefix:
            return None
        prefix = self.archive_prefix.lstrip("/")
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        return prefix


@dataclasses.dataclass
class ClusterOptions:
    template_path: Optional[str] = None
    preferred_availability_zone: Optional[str] = None
    auto_teardown: bool = False
    idle_teardown_minutes: int = 20
    reuse_cluster_name: Optional[str] = None
    contact_email: Optional[str] = None
    repo_tag: Optional[str] = None


@dataclasses.dataclass
class PipelineOptions:
    workdir: str
    stage_command: str
    clone_command: str
    run_prefix: str
    export_command: str
    pipeline_timeout_minutes: Optional[int] = None
    local_stage_root: Optional[str] = None
    reference_bucket: Optional[str] = None
    ssh_identity_file: Optional[str] = None
    ssh_user: str = "ubuntu"
    ssh_extra_args: List[str] = dataclasses.field(default_factory=list)
    login_shell_init: str = "source ~/.bashrc"
    tmux_session_prefix: str = "daylily"
    tmux_keepalive_shell: str = "bash"
    # Local monitor metadata (markers, tmux name) — never /fsx
    local_state_root: Optional[str] = "~/.cache/daylily-monitor"
    # FSx clone base + repo dir name for fallback path computation
    clone_dest_root: str = "/fsx/analysis_results/ubuntu"
    repo_dir_name: str = "daylily-omics-analysis"


@dataclasses.dataclass
class StageArtifacts:
    """Details about staged sample files and manifests."""

    fsx_stage_dir: PurePosixPath
    staged_files: List[PurePosixPath]
    samples_manifest: Optional[PurePosixPath]
    units_manifest: Optional[PurePosixPath]


@dataclasses.dataclass
class WorksetInputs:
    """Configuration and manifest details required to process a workset."""

    manifest_path: Path
    work_yaml: Dict[str, object]
    workdir_name: str
    clone_args: str
    run_suffix: Optional[str]
    target_export_uri: Optional[str]
    budget_name: Optional[str]


@dataclasses.dataclass
class Workset:
    name: str
    prefix: str
    sentinels: Dict[str, str]
    has_required_files: bool = False
    is_archived: bool = False

    def sentinel_timestamp(self, sentinel: str) -> Optional[str]:
        return self.sentinels.get(sentinel)


@dataclasses.dataclass
class WorksetReportRow:
    name: str
    state: str
    timestamp: Optional[str]
    detail: Optional[str]
    has_required_files: bool
    display_state: Optional[str] = None
    metrics: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def state_text(self) -> str:
        return self.display_state or self.state


@dataclasses.dataclass
class MonitorConfig:
    aws: AWSConfig
    monitor: MonitorOptions
    cluster: ClusterOptions
    pipeline: PipelineOptions

    @staticmethod
    def load(path: Path) -> "MonitorConfig":
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        aws_cfg = AWSConfig(**data["aws"])
        monitor_cfg = MonitorOptions(**data["monitor"])
        cluster_cfg = ClusterOptions(**data.get("cluster", {}))
        pipeline_cfg = PipelineOptions(**data["pipeline"])
        return MonitorConfig(
            aws=aws_cfg, monitor=monitor_cfg, cluster=cluster_cfg, pipeline=pipeline_cfg
        )


class WorksetMonitor:
    DEFAULT_ACTION_SEQUENCE: Tuple[str, ...] = (
        "check_state",
        "update_state",
        "stage_data",
        "clone_repo",
        "run_pipeline",
        "export_results",
    )
    OPTIONAL_ACTIONS: Tuple[str, ...] = (
        "monitor_pipeline",
        "cleanup_pipeline",
        "shutdown_cluster",
    )

    def __init__(
        self,
        config: MonitorConfig,
        *,
        dry_run: bool = False,
        debug: bool = False,
        process_directories: Optional[Sequence[str]] = None,
        attempt_restart: bool = False,
        force_recalculate_metrics: bool = False,
        state_db: Optional[Any] = None,
        integration: Optional[Any] = None,
        notification_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the workset monitor.

        Args:
            config: Monitor configuration
            dry_run: If True, don't mutate S3 or execute commands
            debug: Enable debug output
            process_directories: Only process specific workset directories
            attempt_restart: Retry failed worksets
            force_recalculate_metrics: Recalculate all metrics
            state_db: Optional DynamoDB state database for unified state tracking
            integration: Optional WorksetIntegration for unified state operations
            notification_manager: Optional notification manager for alerts
        """
        self.config = config
        self.dry_run = dry_run
        self.debug = debug
        self.attempt_restart = attempt_restart
        self.force_recalculate_metrics = force_recalculate_metrics

        # Integration layer components
        self.state_db = state_db
        self.integration = integration
        self.notification_manager = notification_manager

        self._session = boto3.session.Session(**config.aws.session_kwargs())
        self._s3 = self._session.client("s3")
        self._sts = self._session.client("sts")
        self.lock_owner_id = f"{socket.gethostname()}-{os.getpid()}"
        self._sentinel_history: Dict[str, Dict[str, str]] = {}
        self._process_directories: Optional[Set[str]] = (
            {name.strip() for name in process_directories if name.strip()}
            if process_directories
            else None
        )
        self._headnode_ips: Dict[str, str] = {}
        self._pipeline_locations: Dict[str, PurePosixPath] = {}
        self._stage_artifacts: Dict[str, StageArtifacts] = {}
        self._workset_metrics: Dict[str, Dict[str, Any]] = {}
        self._workdir_names: Dict[str, str] = {}
        self._metrics_script_cache: Optional[str] = None

    # ------------------------------------------------------------------
    # Public entrypoints
    # ------------------------------------------------------------------
    def run(self) -> None:
        LOGGER.info("Starting Daylily workset monitor in %s", self.config.aws.region)
        if self.config.aws.session_duration_seconds:
            self._refresh_session()
        while True:
            start_time = time.time()
            try:
                worksets = list(self._discover_worksets())
                self._update_sentinel_indexes(worksets)
                for workset in worksets:
                    self._handle_workset(workset)
            except Exception:
                LOGGER.exception("Unexpected failure while monitoring worksets")
            elapsed = time.time() - start_time
            sleep_for = max(self.config.monitor.poll_interval_seconds - elapsed, 0)
            if not self.config.monitor.continuous:
                break
            if sleep_for:
                LOGGER.debug("Sleeping %.1fs before next poll", sleep_for)
                time.sleep(sleep_for)

    def perform_actions(
        self,
        actions: Sequence[str],
        *,
        include_archive: bool = False,
    ) -> None:
        if not actions:
            action_sequence = list(self.DEFAULT_ACTION_SEQUENCE)
        else:
            action_sequence = [action.strip().lower() for action in actions if action.strip()]
        valid_actions = set(self.DEFAULT_ACTION_SEQUENCE) | set(self.OPTIONAL_ACTIONS)
        invalid = [action for action in action_sequence if action not in valid_actions]
        if invalid:
            raise MonitorError(f"Unknown monitor actions requested: {', '.join(sorted(invalid))}")

        worksets = list(self._discover_worksets(include_archive=include_archive))
        for workset in worksets:
            if not self._should_process(workset):
                LOGGER.info(
                    "Skipping %s: not selected via --process-directory", workset.name
                )
                continue
            self._execute_requested_actions(workset, action_sequence)

    def _execute_requested_actions(
        self, workset: Workset, actions: Sequence[str]
    ) -> None:
        proceed = True
        inputs: Optional[WorksetInputs] = None
        cluster_name: Optional[str] = None
        pipeline_dir: Optional[PurePosixPath] = None
        stage_artifacts: Optional[StageArtifacts] = None
        session_name: Optional[str] = None

        for action in actions:
            LOGGER.debug("Executing %s for %s", action, workset.name)
            if action == "check_state":
                proceed = self._check_workset_state(workset)
                if not proceed:
                    LOGGER.info("Workset %s did not pass check-state", workset.name)
                    break
                continue

            if action == "update_state":
                if not proceed:
                    LOGGER.info(
                        "Skipping update-state for %s: prior checks failed", workset.name
                    )
                    break
                proceed = self._update_workset_state(workset)
                if not proceed:
                    LOGGER.info(
                        "Unable to acquire workset %s during update-state", workset.name
                    )
                    break
                continue

            # Remaining actions require workset configuration details.
            if inputs is None:
                inputs = self._load_workset_inputs(workset)

            requires_cluster = action in {
                "stage_data",
                "clone_repo",
                "run_pipeline",
                "monitor_pipeline",
                "export_results",
                "cleanup_pipeline",
                "shutdown_cluster",
            }
            if requires_cluster and cluster_name is None:
                cluster_name = self._ensure_cluster(inputs.work_yaml)
                LOGGER.info("Using cluster %s for workset %s", cluster_name, workset.name)
                self._update_metrics(workset, {"cluster_name": cluster_name})

            if action == "stage_data":
                if cluster_name is None:
                    raise MonitorError("Cluster is required to stage data")
                stage_artifacts = self._stage_samples(
                    workset, inputs.manifest_path, cluster_name
                )
                continue

            if action == "clone_repo":
                if cluster_name is None:
                    raise MonitorError("Cluster is required to clone the repository")
                run_clone = bool(inputs.clone_args)
                pipeline_dir = self._prepare_pipeline_workspace(
                    workset,
                    cluster_name,
                    inputs.clone_args,
                    run_clone=run_clone,
                )
                continue

            if action == "run_pipeline":
                if cluster_name is None:
                    raise MonitorError("Cluster is required to run the pipeline")
                if pipeline_dir is None:
                    pipeline_dir = self._prepare_pipeline_workspace(
                        workset,
                        cluster_name,
                        inputs.clone_args,
                        run_clone=bool(inputs.clone_args),
                    )
                if stage_artifacts is None:
                    stage_artifacts = self._stage_artifacts.get(workset.name)
                if stage_artifacts is None:
                    raise MonitorError(
                        "Stage samples output unavailable; run stage-data before run-pipeline"
                    )
                self._push_stage_files_to_pipeline(
                    cluster_name, pipeline_dir, inputs.manifest_path, stage_artifacts
                )
                session_name = self._run_pipeline(
                    workset,
                    cluster_name,
                    pipeline_dir,
                    inputs.run_suffix,
                    monitor=False,
                )
                continue

            if action == "monitor_pipeline":
                if cluster_name is None:
                    raise MonitorError("Cluster is required to monitor the pipeline")
                if pipeline_dir is None:
                    pipeline_dir = self._prepare_pipeline_workspace(
                        workset,
                        cluster_name,
                        inputs.clone_args,
                        run_clone=False,
                    )
                if session_name is None:
                    session_name = self._load_tmux_session(workset)
                if not session_name:
                    raise MonitorError(
                        f"No tmux session recorded for {workset.name}; run run-pipeline first"
                    )
                self._monitor_pipeline_session(
                    workset, cluster_name, pipeline_dir, session_name
                )
                continue

            if action == "export_results":
                if cluster_name is None:
                    raise MonitorError("Cluster is required to export results")
                if not inputs.target_export_uri:
                    raise MonitorError(
                        f"Export URI is not configured for {workset.name}; update daylily_work.yaml"
                    )
                if pipeline_dir is None:
                    pipeline_dir = self._prepare_pipeline_workspace(
                        workset,
                        cluster_name,
                        inputs.clone_args,
                        run_clone=False,
                    )
                self._export_results(
                    workset, cluster_name, inputs.target_export_uri, pipeline_dir
                )
                continue

            if action == "cleanup_pipeline":
                if cluster_name is None:
                    raise MonitorError("Cluster is required to clean up the pipeline")
                if pipeline_dir is None:
                    pipeline_dir = self._prepare_pipeline_workspace(
                        workset,
                        cluster_name,
                        inputs.clone_args,
                        run_clone=False,
                    )
                self._cleanup_pipeline_directory(workset, cluster_name, pipeline_dir)
                pipeline_dir = None
                continue

            if action == "shutdown_cluster":
                if cluster_name is None:
                    cluster_name = self._ensure_cluster(inputs.work_yaml)
                self._shutdown_cluster(cluster_name)
                cluster_name = None

    def build_workset(
        self,
        workset_id: str,
        *,
        prefix: Optional[str] = None,
        sentinels: Optional[Dict[str, str]] = None,
        has_required_files: bool = True,
        is_archived: bool = False,
    ) -> Workset:
        """Create a Workset object for direct processing."""
        normalized_prefix = prefix or f"{self.config.monitor.normalised_prefix()}{workset_id}/"
        return Workset(
            name=workset_id,
            prefix=normalized_prefix,
            sentinels=sentinels or {},
            has_required_files=has_required_files,
            is_archived=is_archived,
        )

    def write_sentinel(self, workset: Workset, sentinel_name: str, value: str) -> None:
        """Public wrapper for writing a sentinel file."""
        self._write_sentinel(workset, sentinel_name, value)

    def load_workset_metrics(self, workset: Workset) -> Dict[str, Any]:
        """Return cached metrics for a workset."""
        return self._load_metrics(workset)

    def process_workset(self, workset: Workset) -> None:
        """Process a workset directly, bypassing S3 sentinel checks."""
        self._process_workset(workset)


    # ------------------------------------------------------------------
    # Workset discovery
    # ------------------------------------------------------------------
    def _discover_worksets(
        self, *, include_archive: bool = False
    ) -> Iterable[Workset]:
        # Track yielded worksets to avoid duplicates
        yielded_names: Set[str] = set()

        # First, discover from S3 (traditional method)
        for workset in self._discover_worksets_for_prefix(
            self.config.monitor.normalised_prefix(), is_archived=False
        ):
            yielded_names.add(workset.name)
            yield workset

        # Also discover from DynamoDB if available (new UI-submitted worksets)
        if self.state_db:
            yield from self._discover_worksets_from_dynamodb(yielded_names)

        if not include_archive:
            return
        archive_prefix = self.config.monitor.normalised_archive_prefix()
        if archive_prefix:
            yield from self._discover_worksets_for_prefix(
                archive_prefix, is_archived=True
            )

    def _discover_worksets_from_dynamodb(
        self, already_yielded: Set[str]
    ) -> Iterable[Workset]:
        """Discover worksets registered in DynamoDB that aren't in S3 yet.

        This enables worksets submitted via the UI to be discovered by the monitor.

        Args:
            already_yielded: Set of workset names already discovered from S3
        """
        if not self.state_db:
            return

        try:
            ready_worksets = self.state_db.get_ready_worksets_prioritized(limit=100)
        except Exception as e:
            LOGGER.warning("Failed to query DynamoDB for worksets: %s", str(e))
            return

        for db_workset in ready_worksets:
            workset_id = db_workset.get("workset_id", "")
            if workset_id in already_yielded:
                continue

            # Convert DynamoDB record to Workset object
            bucket = db_workset.get("bucket", self.config.monitor.bucket)
            prefix = db_workset.get("prefix", f"{self.config.monitor.normalised_prefix()}{workset_id}/")
            state = db_workset.get("state", "ready")
            lock_owner = db_workset.get("lock_owner")
            lock_acquired_at = db_workset.get("lock_acquired_at")

            # Build sentinels dict from DynamoDB state
            sentinels: Dict[str, str] = {}
            created_at = db_workset.get("created_at", "")
            if state == "ready":
                sentinels[SENTINEL_FILES["ready"]] = created_at
            elif state == "in_progress":
                sentinels[SENTINEL_FILES["in_progress"]] = created_at

            if lock_owner:
                sentinels[SENTINEL_FILES["lock"]] = lock_acquired_at or created_at

            # Sync to S3 if integration layer is available
            if self.integration and bucket:
                try:
                    self.integration.sync_dynamodb_to_s3(workset_id)
                    LOGGER.info("Synced DynamoDB workset %s to S3", workset_id)
                except Exception as e:
                    LOGGER.warning("Failed to sync workset %s to S3: %s", workset_id, str(e))

            # Check for required files - pass the correct bucket for customer worksets
            has_required = self._verify_core_files(prefix, bucket=bucket)

            yield Workset(
                name=workset_id,
                prefix=prefix,
                sentinels=sentinels,
                has_required_files=has_required,
                is_archived=False,
            )
            already_yielded.add(workset_id)

    def _discover_worksets_for_prefix(
        self, prefix: str, *, is_archived: bool
    ) -> Iterable[Workset]:
        bucket = self.config.monitor.bucket
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for common_prefix in page.get("CommonPrefixes", []):
                workset_prefix = common_prefix["Prefix"]
                name = workset_prefix.rstrip("/").split("/")[-1]
                sentinels = self._list_sentinels(workset_prefix)
                has_required = self._verify_core_files(workset_prefix)
                yield Workset(
                    name=name,
                    prefix=workset_prefix,
                    sentinels=sentinels,
                    has_required_files=has_required,
                    is_archived=is_archived,
                )

    def _list_sentinels(self, workset_prefix: str) -> Dict[str, str]:
        """List all sentinel files for a workset with pagination safety."""
        bucket = self.config.monitor.bucket
        paginator = self._s3.get_paginator("list_objects_v2")
        sentinel_timestamps: Dict[str, str] = {}
        for page in paginator.paginate(Bucket=bucket, Prefix=workset_prefix):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                if not key.endswith(SENTINEL_SUFFIX):
                    continue
                name = key.split("/")[-1]
                with contextlib.suppress(KeyError):
                    sentinel_timestamps[name] = self._read_object_text(bucket, key)
        return sentinel_timestamps

    def _verify_core_files(self, workset_prefix: str, bucket: Optional[str] = None) -> bool:
        """Verify that a workset directory has all required files.

        Args:
            workset_prefix: S3 prefix for the workset
            bucket: S3 bucket name (defaults to monitor bucket)

        Returns:
            True if all required files are present
        """
        bucket = bucket or self.config.monitor.bucket
        expected = [
            DEFAULT_STAGE_SAMPLES_NAME,
            WORK_YAML_NAME,
            INFO_YAML_NAME,
            SAMPLE_DATA_DIRNAME + "/",
        ]
        found = set()
        all_keys_found = []  # For debugging

        # Normalize prefix to ensure it ends with /
        normalized_prefix = workset_prefix.rstrip("/") + "/" if workset_prefix else ""

        LOGGER.debug(
            "Verifying core files in bucket=%s prefix=%s (normalized from %s)",
            bucket, normalized_prefix, workset_prefix
        )

        paginator = self._s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(
                Bucket=bucket, Prefix=normalized_prefix, Delimiter="/"
            ):
                # Check for sample_data/ directory
                for cp in page.get("CommonPrefixes", []) or []:
                    prefix_name = cp["Prefix"]
                    LOGGER.debug("Found common prefix: %s", prefix_name)
                    if prefix_name.endswith(SAMPLE_DATA_DIRNAME + "/"):
                        found.add(SAMPLE_DATA_DIRNAME + "/")

                # Check for required files
                for obj in page.get("Contents", []) or []:
                    key = obj["Key"]
                    name = key.split("/")[-1]
                    all_keys_found.append(name)
                    if name in (DEFAULT_STAGE_SAMPLES_NAME, WORK_YAML_NAME, INFO_YAML_NAME):
                        found.add(name)
                        LOGGER.debug("Found required file: %s", name)
        except Exception as e:
            LOGGER.error(
                "Error listing S3 objects for workset %s: %s", workset_prefix, e
            )
            return False

        missing = set(expected) - found
        if missing:
            LOGGER.warning(
                "Workset %s missing expected files: %s (found: %s, all files: %s)",
                workset_prefix,
                ", ".join(sorted(missing)),
                ", ".join(sorted(found)) if found else "none",
                ", ".join(sorted(all_keys_found)[:10]) if all_keys_found else "none",
            )
            return False

        LOGGER.debug("Workset %s has all required files: %s", workset_prefix, ", ".join(sorted(found)))
        return True

    # ------------------------------------------------------------------
    # Clone/run helpers (templating + FSx path fallback)
    # ------------------------------------------------------------------
    def _sanitize_name(self, s: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]", "_", s)

    def _workdir_name(self, workset: Workset, work_yaml: Dict[str, object]) -> str:
        wd = work_yaml.get("workdir_name")
        if isinstance(wd, str) and wd.strip():
            return self._sanitize_name(wd.strip())
        return self._sanitize_name(workset.name)

    def _resolve_workdir_name(self, workset: Workset) -> str:
        cached = self._workdir_names.get(workset.name)
        if cached:
            return cached

        metrics = self._load_metrics(workset)
        stored = metrics.get("workdir_name") if isinstance(metrics, dict) else None
        if isinstance(stored, str) and stored.strip():
            resolved = self._sanitize_name(stored.strip())
            self._workdir_names[workset.name] = resolved
            return resolved

        location = self._load_pipeline_location(workset)
        if location:
            repo_dir = self.config.pipeline.repo_dir_name.strip("/")
            candidate: Optional[str]
            if repo_dir and location.name == repo_dir:
                candidate = location.parent.name if location.parent != location else None
            else:
                candidate = location.name
            if candidate:
                resolved = self._sanitize_name(candidate)
                self._workdir_names[workset.name] = resolved
                return resolved

        resolved = self._sanitize_name(workset.name)
        self._workdir_names[workset.name] = resolved
        return resolved

    def _format_clone_args(
        self, clone_args: str, workset: Workset, work_yaml: Dict[str, object]
    ) -> str:
        if not clone_args:
            return ""
        mapping = {
            "workset": workset.name,
            "workdir_name": self._workdir_name(workset, work_yaml),
        }
        try:
            return clone_args.format(**mapping)
        except Exception:
            return clone_args

    def _extract_dest_from_clone_args(self, clone_args: str) -> Optional[str]:
        if not clone_args:
            return None
        parts = shlex.split(clone_args)
        for i, tok in enumerate(parts):
            if tok in ("-d", "--dest", "--destination"):
                if i + 1 < len(parts):
                    return self._sanitize_name(parts[i + 1])
            if tok.startswith("-d="):
                return self._sanitize_name(tok.split("=", 1)[1])
        return None

    def _expected_pipeline_dir(self, dest_name: str) -> PurePosixPath:
        root = self.config.pipeline.clone_dest_root.rstrip("/")
        repo = self.config.pipeline.repo_dir_name.strip("/")
        return PurePosixPath(f"{root}/{dest_name}/{repo}")

    # ------------------------------------------------------------------
    # Sentinel logging
    # ------------------------------------------------------------------
    def _update_sentinel_indexes(self, worksets: Sequence[Workset]) -> None:
        states: Dict[str, List[str]] = defaultdict(list)
        for workset in worksets:
            for sentinel, timestamp in workset.sentinels.items():
                if sentinel in OPTIONAL_SENTINELS or sentinel == SENTINEL_FILES["ready"]:
                    states[sentinel].append(f"{workset.name}\t{timestamp}")
        if not self.config.monitor.sentinel_index_prefix:
            return
        bucket = self.config.monitor.bucket
        base_prefix = self.config.monitor.sentinel_index_prefix
        base_prefix = base_prefix.rstrip("/") + "/" if base_prefix else ""
        for sentinel_name, rows in states.items():
            key = f"{base_prefix}{sentinel_name}.log"
            body = "\n".join(sorted(rows)).encode("utf-8")
            LOGGER.debug(
                "Updating sentinel index %s with %d entries", key, len(rows)
            )
            if self.dry_run:
                continue
            self._s3.put_object(Bucket=bucket, Key=key, Body=body)

    # ------------------------------------------------------------------
    # Workset state machine
    # ------------------------------------------------------------------
    def _check_workset_state(self, workset: Workset) -> bool:
        if not self._should_process(workset):
            LOGGER.info(
                "Skipping %s: not selected via --process-directory", workset.name
            )
            return False
        sentinels = workset.sentinels
        if not sentinels:
            LOGGER.info("Skipping %s: no sentinel files present", workset.name)
            return False
        if SENTINEL_FILES["ignore"] in sentinels:
            LOGGER.info("Skipping %s: daylily.ignore present", workset.name)
            return False
        if SENTINEL_FILES["complete"] in sentinels:
            LOGGER.info(
                "Skipping %s: already complete (at %s)",
                workset.name,
                sentinels[SENTINEL_FILES["complete"]],
            )
            return False
        if SENTINEL_FILES["error"] in sentinels and not self.attempt_restart:
            LOGGER.info(
                "Skipping %s: previously errored at %s",
                workset.name,
                sentinels[SENTINEL_FILES["error"]],
            )
            return False
        if SENTINEL_FILES["in_progress"] in sentinels:
            LOGGER.info(
                "Skipping %s: currently marked in-progress (since %s)",
                workset.name,
                sentinels[SENTINEL_FILES["in_progress"]],
            )
            return False
        if SENTINEL_FILES["ready"] not in sentinels:
            LOGGER.info("Skipping %s: ready sentinel missing", workset.name)
            return False
        if not workset.has_required_files:
            LOGGER.warning("Skipping %s: required files missing", workset.name)
            return False
        return True

    def _update_workset_state(self, workset: Workset) -> bool:
        sentinels = workset.sentinels
        if SENTINEL_FILES["error"] in sentinels and self.attempt_restart:
            error_ts = sentinels[SENTINEL_FILES["error"]]
            LOGGER.info(
                "Retrying %s: clearing error sentinel recorded at %s due to --attempt-restart",
                workset.name,
                error_ts,
            )
            self._delete_sentinel(workset, SENTINEL_FILES["error"])
            sentinels.pop(SENTINEL_FILES["error"], None)
            cleared: List[str] = []
            for stale in (SENTINEL_FILES["lock"], SENTINEL_FILES["in_progress"]):
                if stale in sentinels:
                    self._delete_sentinel(workset, stale)
                    sentinels.pop(stale, None)
                    cleared.append(stale)
            if cleared:
                LOGGER.debug(
                    "Removed stale sentinels for %s during restart: %s",
                    workset.name,
                    ", ".join(sorted(cleared)),
                )

        LOGGER.info("Attempting to acquire ready workset %s", workset.name)
        acquired = self._attempt_acquire(workset)
        if not acquired:
            LOGGER.info(
                "Workset %s lock attempt failed (contention or changed state)",
                workset.name,
            )
            return False
        return True

    def _release_workset_lock(self, workset: Workset) -> None:
        """Release both DynamoDB lock and S3 lock sentinel.

        This should be called after workset processing completes (success or error).
        The lock sentinel is always removed; DynamoDB lock is released if state_db is configured.
        """
        # Delete the S3 lock sentinel
        if SENTINEL_FILES["lock"] in workset.sentinels:
            self._delete_sentinel(workset, SENTINEL_FILES["lock"])
            workset.sentinels.pop(SENTINEL_FILES["lock"], None)
            LOGGER.debug("Removed S3 lock sentinel for %s", workset.name)

        # Release DynamoDB lock if configured
        if self.state_db:
            try:
                released = self.state_db.release_lock(workset.name, self.lock_owner_id)
                if released:
                    LOGGER.info("Released DynamoDB lock for %s", workset.name)
                else:
                    LOGGER.warning(
                        "DynamoDB lock for %s was not held by this owner (%s)",
                        workset.name,
                        self.lock_owner_id,
                    )
            except Exception as e:
                LOGGER.warning(
                    "Failed to release DynamoDB lock for %s: %s", workset.name, str(e)
                )

    def _handle_workset(self, workset: Workset) -> None:
        if not self._check_workset_state(workset):
            return
        if not self._update_workset_state(workset):
            return
        try:
            self._process_workset(workset)
        except Exception as exc:
            LOGGER.exception("Processing of %s failed", workset.name)
            error_msg = f"{dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}\t{exc}"
            self._write_sentinel(
                workset,
                SENTINEL_FILES["error"],
                error_msg,
            )
            # Send notification on failure
            self._notify_workset_event(
                workset.name,
                event_type="error",
                state="error",
                message=f"Workset {workset.name} processing failed",
                error_details=str(exc),
            )
        else:
            self._write_sentinel(
                workset,
                SENTINEL_FILES["complete"],
                dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            # Send notification on completion
            self._notify_workset_event(
                workset.name,
                event_type="completion",
                state="complete",
                message=f"Workset {workset.name} completed successfully",
            )
        finally:
            # Always release the lock after processing (success or error)
            self._release_workset_lock(workset)

    def _notify_workset_event(
        self,
        workset_id: str,
        event_type: str,
        state: str,
        message: str,
        error_details: Optional[str] = None,
    ) -> None:
        """Send notification for workset event.

        Args:
            workset_id: Workset identifier
            event_type: Type of event (state_change, error, completion)
            state: Current workset state
            message: Event message
            error_details: Error details if applicable
        """
        if not self.notification_manager:
            return

        try:
            from daylib.workset_notifications import NotificationEvent

            event = NotificationEvent(
                workset_id=workset_id,
                event_type=event_type,
                state=state,
                message=message,
                error_details=error_details,
            )
            self.notification_manager.notify(event)
        except Exception as e:
            LOGGER.warning("Failed to send notification for %s: %s", workset_id, str(e))

    def _attempt_acquire(self, workset: Workset) -> bool:
        initial_snapshot = dict(workset.sentinels)
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        if self.state_db:
            try:
                acquired = self.state_db.acquire_lock(workset.name, self.lock_owner_id)
            except Exception as exc:
                LOGGER.warning(
                    "Failed to acquire DynamoDB lock for %s: %s",
                    workset.name,
                    str(exc),
                )
                return False
            if not acquired:
                LOGGER.info(
                    "DynamoDB lock already held for %s; skipping S3 lock sentinel",
                    workset.name,
                )
                return False
        self._write_sentinel(workset, SENTINEL_FILES["lock"], timestamp)
        workset.sentinels[SENTINEL_FILES["lock"]] = timestamp
        LOGGER.debug("Wrote lock sentinel for %s", workset.name)
        time.sleep(self.config.monitor.ready_lock_backoff_seconds)
        refreshed = self._list_sentinels(workset.prefix)
        unexpected = set(refreshed) - set(initial_snapshot)
        # If anything else changed besides our lock, treat as contention and back off (no error).
        if unexpected - {SENTINEL_FILES["lock"]}:
            LOGGER.warning(
                "Detected competing sentinel update for %s: %s",
                workset.name,
                ", ".join(sorted(unexpected)),
            )
            self._delete_sentinel(workset, SENTINEL_FILES["lock"])
            if self.state_db:
                self.state_db.release_lock(workset.name, self.lock_owner_id)
            return False
        LOGGER.info("Acquired workset %s", workset.name)
        in_progress_value = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        self._write_sentinel(
            workset,
            SENTINEL_FILES["in_progress"],
            in_progress_value,
        )
        workset.sentinels[SENTINEL_FILES["in_progress"]] = in_progress_value
        return True

    # ------------------------------------------------------------------
    # Workset processing pipeline
    # ------------------------------------------------------------------
    def _load_workset_inputs(self, workset: Workset) -> WorksetInputs:
        manifest_bytes = self._read_required_object(
            workset.prefix, DEFAULT_STAGE_SAMPLES_NAME
        )
        self._validate_stage_manifest(manifest_bytes, workset)
        manifest_path = self._write_temp_file(
            workset, DEFAULT_STAGE_SAMPLES_NAME, manifest_bytes
        )
        manifest_path = self._copy_manifest_to_local(workset, manifest_path)

        work_yaml_bytes = self._read_required_object(workset.prefix, WORK_YAML_NAME)
        work_yaml = yaml.safe_load(work_yaml_bytes.decode("utf-8"))

        workdir_name = self._workdir_name(workset, work_yaml)
        self._workdir_names[workset.name] = workdir_name
        self._update_metrics(workset, {"workdir_name": workdir_name})

        budget_name_raw = work_yaml.get("budget")
        budget_name = budget_name_raw.strip() if isinstance(budget_name_raw, str) else None
        if budget_name:
            self._update_metrics(workset, {"budget": budget_name})

        clone_args_raw = self._yaml_get_str(
            work_yaml,
            ["day_clone_args", "day-clone", "clone_args", "clone-args", "clone"],
        ) or ""
        clone_args = self._format_clone_args(clone_args_raw, workset, work_yaml)
        if budget_name:
            append = f" --budget {shlex.quote(budget_name)}"
            clone_args = (clone_args + append).strip()

        run_suffix = self._yaml_get_str(
            work_yaml,
            [
                "dy_r",
                "dy-r",
                "dy",
                "run",
                "run_suffix",
                "run-suffix",
                "run_cmd",
                "run-command",
            ],
        )

        target_export_uri = self._yaml_get_str(
            work_yaml, ["export_uri", "export-uri", "export"]
        )

        return WorksetInputs(
            manifest_path=manifest_path,
            work_yaml=work_yaml,
            workdir_name=workdir_name,
            clone_args=clone_args,
            run_suffix=run_suffix,
            target_export_uri=target_export_uri,
            budget_name=budget_name,
        )

    def _process_workset(self, workset: Workset) -> None:
        inputs = self._load_workset_inputs(workset)
        cluster_name = self._ensure_cluster(inputs.work_yaml)
        LOGGER.info("Using cluster %s for workset %s", cluster_name, workset.name)
        self._update_metrics(workset, {"cluster_name": cluster_name})

        completed_commands: Set[str] = set()
        clone_args = inputs.clone_args
        manifest_path = inputs.manifest_path
        run_suffix = inputs.run_suffix
        target_export_uri = inputs.target_export_uri

        if clone_args:
            pipeline_dir: Optional[PurePosixPath] = None
        else:
            # No clone; ensure fallback dir on headnode
            pipeline_dir = self._prepare_pipeline_workspace(
                workset, cluster_name, clone_args, run_clone=False
            )

        retry_attempted = False
        while True:
            try:
                pipeline_dir = self._execute_workset_commands(
                    workset,
                    manifest_path,
                    cluster_name,
                    clone_args,
                    run_suffix,
                    target_export_uri,
                    pipeline_dir,
                    completed_commands,
                )
                break
            except CommandFailedError as exc:
                if not self.attempt_restart or retry_attempted:
                    raise
                retry_attempted = True
                LOGGER.warning(
                    "Command %s failed for %s; attempting restart from this command",
                    exc.command_label,
                    workset.name,
                )
                continue

    def _execute_workset_commands(
        self,
        workset: Workset,
        manifest_path: Path,
        cluster_name: str,
        clone_args: str,
        run_suffix: Optional[str],
        target_export_uri: Optional[str],
        pipeline_dir: Optional[PurePosixPath],
        completed_commands: Set[str],
    ) -> PurePosixPath:
        stage_label = "stage_samples"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            if stage_label in completed_commands:
                LOGGER.info(
                    "Skipping sample staging for %s: command already completed",
                    workset.name,
                )
                stage_future = executor.submit(
                    lambda: self._stage_artifacts.get(workset.name)
                )
            else:
                stage_future = executor.submit(
                    self._stage_samples, workset, manifest_path, cluster_name
                )
            cluster_future = executor.submit(
                self._wait_for_cluster_ready, cluster_name
            )
            cluster_details = cluster_future.result()
            if cluster_details:
                zone = self._extract_cluster_zone(cluster_details)
                if zone:
                    self._update_metrics(workset, {"region_az": zone})
            try:
                stage_artifacts = stage_future.result()
            except CommandFailedError:
                raise
        if stage_artifacts is None:
            stage_artifacts = self._stage_artifacts.get(workset.name)
        if stage_artifacts is None:
            raise MonitorError(
                f"Stage samples output unavailable for {workset.name}; rerun staging"
            )
        completed_commands.add(stage_label)

        clone_label = "clone_pipeline"
        clone_needed = bool(clone_args) and clone_label not in completed_commands
        if clone_needed:
            LOGGER.info("Running pipeline clone for %s", workset.name)
            pipeline_dir = self._prepare_pipeline_workspace(
                workset, cluster_name, clone_args, run_clone=True
            )
            completed_commands.add(clone_label)
        elif clone_args:
            LOGGER.info(
                "Skipping pipeline clone for %s: command already completed",
                workset.name,
            )
            if pipeline_dir is None:
                pipeline_dir = self._prepare_pipeline_workspace(
                    workset, cluster_name, clone_args, run_clone=False
                )

        if pipeline_dir is None:
            raise MonitorError(
                "Pipeline directory unavailable; rerun day-clone or remove cached state"
            )

        push_label = "push_stage_files"
        if push_label in completed_commands:
            LOGGER.info(
                "Skipping stage file push for %s: command already completed",
                workset.name,
            )
        else:
            self._push_stage_files_to_pipeline(
                cluster_name, pipeline_dir, manifest_path, stage_artifacts
            )
            completed_commands.add(push_label)

        run_label = "run_pipeline"
        if run_label in completed_commands:
            LOGGER.info(
                "Skipping pipeline run for %s: command already completed",
                workset.name,
            )
        else:
            self._run_pipeline(workset, cluster_name, pipeline_dir, run_suffix)
            completed_commands.add(run_label)

        if target_export_uri:
            export_label = "export_results"
            if export_label in completed_commands:
                LOGGER.info(
                    "Skipping export for %s: command already completed", workset.name
                )
            else:
                self._export_results(
                    workset, cluster_name, target_export_uri, pipeline_dir
                )
                completed_commands.add(export_label)

        return pipeline_dir

    def _local_state_dir(self, workset: Workset) -> Path:
        root = self.config.pipeline.local_state_root or "~/.cache/daylily-monitor"
        path = Path(os.path.expanduser(root)) / workset.name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _metrics_file(self, workset: Workset) -> Path:
        return self._local_state_dir(workset) / "report_metrics.json"

    def _load_metrics(self, workset: Workset) -> Dict[str, Any]:
        cached = self._workset_metrics.get(workset.name)
        if cached is not None:
            return cached
        path = self._metrics_file(workset)
        data: Dict[str, Any]
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
        self._workset_metrics[workset.name] = data
        return data

    def _save_metrics(self, workset: Workset, data: Dict[str, Any]) -> None:
        path = self._metrics_file(workset)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        self._workset_metrics[workset.name] = data

    def _update_metrics(self, workset: Workset, updates: Dict[str, Any]) -> Dict[str, Any]:
        data = self._load_metrics(workset)
        changed = False
        for key, value in updates.items():
            if value is None:
                continue
            if data.get(key) != value:
                data[key] = value
                changed = True
        if changed:
            self._save_metrics(workset, data)
        return data

    def _parse_timestamp(self, value: Optional[str]) -> Optional[dt.datetime]:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z") and not text.endswith("+00:00"):
            text = text[:-1] + "+00:00"
        try:
            return dt.datetime.fromisoformat(text)
        except ValueError:
            return None

    def _normalise_timestamp(self, value: Optional[str]) -> Optional[str]:
        parsed = self._parse_timestamp(value)
        if not parsed:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        else:
            parsed = parsed.astimezone(dt.timezone.utc)
        parsed = parsed.replace(microsecond=0)
        return parsed.isoformat().replace("+00:00", "Z")

    def _update_runtime_metric(
        self,
        workset: Workset,
        metrics: Dict[str, Any],
        *,
        end_timestamp: Optional[str] = None,
    ) -> None:
        start_value = metrics.get("start_dt")
        end_value = end_timestamp or metrics.get("end_dt")
        if not start_value or not end_value:
            return
        start_dt = self._parse_timestamp(start_value)
        end_dt = self._parse_timestamp(end_value)
        if not start_dt or not end_dt:
            return
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=dt.timezone.utc)
        else:
            start_dt = start_dt.astimezone(dt.timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=dt.timezone.utc)
        else:
            end_dt = end_dt.astimezone(dt.timezone.utc)
        runtime = max(0.0, (end_dt - start_dt).total_seconds())
        if metrics.get("runtime_seconds") != runtime:
            metrics["runtime_seconds"] = runtime
            self._save_metrics(workset, metrics)

    def _record_terminal_metrics(
        self, workset: Workset, sentinel_name: str, value: str
    ) -> None:
        terminal_map = {
            SENTINEL_FILES["complete"]: "complete",
            SENTINEL_FILES["error"]: "error",
            SENTINEL_FILES["ignore"]: "ignored",
        }
        state = terminal_map.get(sentinel_name)
        if not state:
            return
        timestamp, _, *_ = value.partition("\t")
        normalised = self._normalise_timestamp(timestamp.strip()) or timestamp.strip()
        metrics = self._update_metrics(
            workset,
            {
                "end_dt": normalised,
                "terminal_state": state,
            },
        )
        self._update_runtime_metric(workset, metrics, end_timestamp=normalised)

    def _metrics_script_text(self) -> str:
        if self._metrics_script_cache is not None:
            return self._metrics_script_cache
        try:
            script_path = resources.files("daylib").joinpath("workset_metrics.py")
            with script_path.open("r", encoding="utf-8") as handle:
                self._metrics_script_cache = handle.read()
        except (FileNotFoundError, AttributeError):
            self._metrics_script_cache = ""
        return self._metrics_script_cache

    def _metrics_args(self, pipeline_dir: PurePosixPath) -> List[str]:
        args: List[str] = []
        if self.debug:
            args.append("--debug")
        args.append(str(pipeline_dir))
        return args

    def _should_refresh_remote_metrics(
        self, metrics: Dict[str, Any], *, is_terminal: bool
    ) -> bool:
        if is_terminal and metrics.get("terminal_cached"):
            return False
        timestamp = metrics.get("remote_metrics_timestamp")
        if not timestamp:
            return True
        parsed = self._parse_timestamp(timestamp)
        if not parsed:
            return True
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(dt.timezone.utc)
        else:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        now = dt.datetime.now(dt.timezone.utc)
        age = (now - parsed).total_seconds()
        if is_terminal:
            return not metrics.get("terminal_cached")
        return age >= 300

    def _fetch_remote_metrics(
        self,
        workset: Workset,
        *,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
    ) -> Optional[Dict[str, Any]]:
        script = self._metrics_script_text()
        if not script:
            LOGGER.debug("Metrics script unavailable; skipping remote metrics for %s", workset.name)
            return None
        command = (
            "python3 - <<'PY'\n"
            f"{script}\n"
            "if __name__ == '__main__':\n"
            f"    main([{', '.join(json.dumps(arg) for arg in self._metrics_args(pipeline_dir))}])\n"
            "PY"
        )
        result = self._run_headnode_command(
            cluster_name,
            command,
            check=False,
            shell=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore").strip()
            LOGGER.debug(
                "Remote metrics command exited %s for %s: %s",
                result.returncode,
                workset.name,
                stderr,
            )
            return None
        stdout = result.stdout.decode("utf-8", errors="ignore").strip()
        data: Optional[Dict[str, Any]] = None
        for line in reversed(stdout.splitlines() or [stdout]):
            line = line.strip()
            if not line:
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                data = candidate
                break
        if not data:
            LOGGER.debug("Unable to parse remote metrics output for %s: %s", workset.name, stdout)
            return None
        refreshed = self._normalise_timestamp(dt.datetime.now(dt.timezone.utc).isoformat())
        if refreshed:
            data["remote_metrics_timestamp"] = refreshed
        return data

    def _gather_workset_metrics(
        self, workset: Workset, row: WorksetReportRow
    ) -> Dict[str, Any]:
        metrics = self._load_metrics(workset)
        updated = False

        if row.timestamp and not metrics.get("start_dt"):
            normalised = self._normalise_timestamp(row.timestamp)
            if normalised:
                metrics["start_dt"] = normalised
                updated = True

        pipeline_dir_str = metrics.get("pipeline_dir")
        if not pipeline_dir_str:
            location = self._load_pipeline_location(workset)
            if location:
                metrics["pipeline_dir"] = str(location)
                pipeline_dir_str = str(location)
                updated = True

        cluster_name_raw = metrics.get("cluster_name")
        cluster_name: Optional[str] = str(cluster_name_raw) if cluster_name_raw else None
        is_terminal = row.state in {"complete", "error", "ignored"}

        remote_required_keys = [
            "samples_count",
            "sample_library_count",
            "fastq_count",
            "fastq_size_bytes",
            "cram_count",
            "cram_size_bytes",
            "vcf_count",
            "vcf_size_bytes",
            "results_size_bytes",
            "s3_daily_cost_usd",
            "cram_transfer_cross_region_cost",
            "cram_transfer_internet_cost",
            "vcf_transfer_cross_region_cost",
            "vcf_transfer_internet_cost",
            "ec2_cost_usd",
        ]

        need_remote = any(key not in metrics for key in remote_required_keys)
        if self.force_recalculate_metrics:
            need_remote = True
        should_refresh = False
        if cluster_name and pipeline_dir_str:
            if self.force_recalculate_metrics:
                should_refresh = True
            else:
                should_refresh = need_remote or self._should_refresh_remote_metrics(
                    metrics, is_terminal=is_terminal
                )
        if should_refresh and pipeline_dir_str and cluster_name:
            remote = self._fetch_remote_metrics(
                workset,
                cluster_name=cluster_name,
                pipeline_dir=PurePosixPath(pipeline_dir_str),
            )
            if remote:
                for key, value in remote.items():
                    if self.force_recalculate_metrics:
                        if value is None:
                            continue
                        if metrics.get(key) != value or key not in metrics:
                            updated = True
                        metrics[key] = value
                    else:
                        if metrics.get(key) != value:
                            metrics[key] = value
                            updated = True
                if is_terminal and metrics.get("terminal_cached") is not True:
                    metrics["terminal_cached"] = True
                    updated = True
            elif not is_terminal:
                if metrics.pop("remote_metrics_timestamp", None) is not None:
                    updated = True

        if not is_terminal and metrics.get("terminal_cached"):
            metrics.pop("terminal_cached", None)
            updated = True

        if metrics.get("start_dt") and metrics.get("end_dt"):
            self._update_runtime_metric(workset, metrics)

        if updated:
            self._save_metrics(workset, metrics)
        return metrics

    def _format_timestamp_for_display(self, value: Optional[str]) -> str:
        normalised = self._normalise_timestamp(value)
        return normalised or ""

    def _format_runtime(self, seconds: Optional[float]) -> str:
        if seconds is None:
            return ""
        try:
            total = int(max(0, float(seconds)))
        except (TypeError, ValueError):
            return ""
        return str(dt.timedelta(seconds=total))

    def _format_size_gb(self, value: Optional[Any]) -> str:
        if value is None or value == "":
            return ""
        try:
            gb = float(str(value)) / (1024 ** 3)
        except (TypeError, ValueError):
            return ""
        return f"{gb:.2f} GB"

    def _format_currency(self, value: Optional[Any]) -> str:
        if value is None or value == "":
            return ""
        try:
            amount = float(str(value))
        except (TypeError, ValueError):
            return ""
        return f"${amount:.2f}"

    def _format_transfer_cost(
        self, cross_region: Optional[Any], internet: Optional[Any]
    ) -> str:
        if cross_region in (None, "") and internet in (None, ""):
            return ""
        return " / ".join(
            filter(
                None,
                (
                    self._format_currency(cross_region),
                    self._format_currency(internet),
                ),
            )
        )

    def _string_or_empty(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _calculate_runtime_seconds(
        self, metrics: Dict[str, Any], state: str
    ) -> Optional[float]:
        terminal_states = {"complete", "error", "ignored"}
        if state in terminal_states and metrics.get("runtime_seconds") is not None:
            try:
                return float(metrics["runtime_seconds"])
            except (TypeError, ValueError):
                return None
        start = self._parse_timestamp(metrics.get("start_dt"))
        if not start:
            return None
        if start.tzinfo is None:
            start = start.replace(tzinfo=dt.timezone.utc)
        else:
            start = start.astimezone(dt.timezone.utc)
        end_value = metrics.get("end_dt") if state in terminal_states else None
        if end_value:
            end = self._parse_timestamp(end_value)
        else:
            end = None
        if end:
            if end.tzinfo is None:
                end = end.replace(tzinfo=dt.timezone.utc)
            else:
                end = end.astimezone(dt.timezone.utc)
        else:
            end = dt.datetime.now(dt.timezone.utc)
        runtime = (end - start).total_seconds()
        return max(0.0, runtime)

    def _prepare_report_table(
        self, rows: Sequence[WorksetReportRow], *, min_details: bool
    ) -> Tuple[List[str], List[List[str]]]:
        table_rows: List[List[str]] = []
        if min_details:
            headers = ["Workset", "State", "StartDT", "Valid", "Detail"]
        else:
            headers = [
                "Workset",
                "State",
                "StartDT",
                "EndDT",
                "RunTime",
                "Valid",
                "Cluster",
                "RegionAZ",
                "Budget",
                "PipelineCmd",
                "CloneCmd",
                "NumSamps",
                "NumSampLibs",
                "NumFASTQs",
                "FASTQSize",
                "NumCRAMs",
                "CRAMSize",
                "NumVCFs",
                "VCFSize",
                "ResultsSize",
                "S3DailyCost",
                "CRAMTransferCost",
                "VCFTransferCost",
                "EC2Cost",
                "Detail",
            ]

        for row in rows:
            metrics = row.metrics or {}
            start_dt = metrics.get("start_dt") or row.timestamp
            start_text = self._format_timestamp_for_display(start_dt)
            valid_text = "yes" if row.has_required_files else "no"
            detail_text = row.detail or ""
            if min_details:
                table_rows.append(
                    [
                        row.name,
                        row.state_text,
                        start_text,
                        valid_text,
                        detail_text,
                    ]
                )
                continue

            end_text = self._format_timestamp_for_display(metrics.get("end_dt"))
            runtime_seconds = self._calculate_runtime_seconds(metrics, row.state)
            runtime_text = self._format_runtime(runtime_seconds)
            table_rows.append(
                [
                    row.name,
                    row.state_text,
                    start_text,
                    end_text,
                    runtime_text,
                    valid_text,
                    self._string_or_empty(metrics.get("cluster_name")),
                    self._string_or_empty(metrics.get("region_az")),
                    self._string_or_empty(metrics.get("budget")),
                    self._string_or_empty(metrics.get("pipeline_command")),
                    self._string_or_empty(metrics.get("clone_command")),
                    self._string_or_empty(metrics.get("samples_count")),
                    self._string_or_empty(metrics.get("sample_library_count")),
                    self._string_or_empty(metrics.get("fastq_count")),
                    self._format_size_gb(metrics.get("fastq_size_bytes")),
                    self._string_or_empty(metrics.get("cram_count")),
                    self._format_size_gb(metrics.get("cram_size_bytes")),
                    self._string_or_empty(metrics.get("vcf_count")),
                    self._format_size_gb(metrics.get("vcf_size_bytes")),
                    self._format_size_gb(metrics.get("results_size_bytes")),
                    self._format_currency(metrics.get("s3_daily_cost_usd")),
                    self._format_transfer_cost(
                        metrics.get("cram_transfer_cross_region_cost"),
                        metrics.get("cram_transfer_internet_cost"),
                    ),
                    self._format_transfer_cost(
                        metrics.get("vcf_transfer_cross_region_cost"),
                        metrics.get("vcf_transfer_internet_cost"),
                    ),
                    self._format_currency(metrics.get("ec2_cost_usd")),
                    detail_text,
                ]
            )

        return headers, table_rows

    def _cluster_state_dir(self, cluster_name: str) -> Path:
        root = self.config.pipeline.local_state_root or "~/.cache/daylily-monitor"
        path = Path(os.path.expanduser(root)) / CLUSTER_STATE_DIR / cluster_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _cluster_idle_marker(self, cluster_name: str) -> Path:
        return self._cluster_state_dir(cluster_name) / CLUSTER_IDLE_MARKER

    def _clear_cluster_idle(self, cluster_name: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            self._cluster_idle_marker(cluster_name).unlink()

    def _record_pipeline_location(
        self, workset: Workset, location: PurePosixPath
    ) -> None:
        self._pipeline_locations[workset.name] = location
        state_dir = self._local_state_dir(workset)
        marker = state_dir / PIPELINE_LOCATION_MARKER
        marker.write_text(str(location), encoding="utf-8")
        self._update_metrics(workset, {"pipeline_dir": str(location)})

    def _load_pipeline_location(self, workset: Workset) -> Optional[PurePosixPath]:
        cached = self._pipeline_locations.get(workset.name)
        if cached:
            return cached
        marker = self._local_state_dir(workset) / PIPELINE_LOCATION_MARKER
        if not marker.exists():
            return None
        text = marker.read_text(encoding="utf-8").strip()
        if not text:
            return None
        location = PurePosixPath(text)
        self._pipeline_locations[workset.name] = location
        return location

    def _clear_pipeline_location(self, workset: Workset) -> None:
        self._pipeline_locations.pop(workset.name, None)
        marker = self._local_state_dir(workset) / PIPELINE_LOCATION_MARKER
        with contextlib.suppress(FileNotFoundError):
            marker.unlink()
        self._update_metrics(workset, {"pipeline_dir": None})

    def _parse_day_clone_location(self, output: bytes) -> Optional[PurePosixPath]:
        text = output.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("location"):
                _, _, remainder = stripped.partition(":")
                candidate = remainder.strip()
                if candidate:
                    return PurePosixPath(candidate)
            if stripped.startswith("cd "):
                parts = shlex.split(stripped)
                if len(parts) >= 2:
                    return PurePosixPath(parts[1])
        return None

    def _record_tmux_session(self, workset: Workset, session_name: str) -> None:
        state_dir = self._local_state_dir(workset)
        marker = state_dir / PIPELINE_SESSION_MARKER
        marker.write_text(session_name, encoding="utf-8")

    def _generate_tmux_session_name(self, workset: Workset) -> str:
        prefix = self.config.pipeline.tmux_session_prefix or "daylily"
        safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "_", prefix)
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", workset.name)
        timestamp = int(time.time())
        return f"{safe_prefix}_{safe_name}_{timestamp}"

    def _load_tmux_session(self, workset: Workset) -> Optional[str]:
        marker = self._local_state_dir(workset) / PIPELINE_SESSION_MARKER
        if not marker.exists():
            return None
        session_name = marker.read_text(encoding="utf-8").strip()
        return session_name or None

    def _clear_tmux_session(self, workset: Workset) -> None:
        marker = self._local_state_dir(workset) / PIPELINE_SESSION_MARKER
        with contextlib.suppress(FileNotFoundError):
            marker.unlink()

    def _pipeline_start_marker(self, workset: Workset) -> Path:
        return self._local_state_dir(workset) / PIPELINE_START_MARKER

    def _record_pipeline_start(self, workset: Workset, timestamp: dt.datetime) -> None:
        marker = self._pipeline_start_marker(workset)
        cleaned = timestamp.replace(microsecond=0).isoformat()
        normalised = self._normalise_timestamp(cleaned) or cleaned
        marker.write_text(normalised, encoding="utf-8")
        self._update_metrics(workset, {"start_dt": normalised})

    def _load_pipeline_start(self, workset: Workset) -> Optional[dt.datetime]:
        marker = self._pipeline_start_marker(workset)
        if not marker.exists():
            return None
        text = marker.read_text(encoding="utf-8").strip()
        if not text:
            return None
        parsed = self._parse_timestamp(text)
        if not parsed:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed

    def _clear_pipeline_start(self, workset: Workset) -> None:
        with contextlib.suppress(FileNotFoundError):
            self._pipeline_start_marker(workset).unlink()

    def _validate_stage_manifest(
        self, manifest_bytes: bytes, workset: Workset
    ) -> None:
        lines = manifest_bytes.decode("utf-8").splitlines()
        if not lines:
            raise MonitorError(f"stage_samples.tsv for {workset.name} is empty")
        header = lines[0].split("\t")
        s3_columns = [
            idx
            for idx, name in enumerate(header)
            if name.lower().endswith("_uri") or name.lower().startswith("s3")
        ]
        sample_data_columns = [
            idx
            for idx, name in enumerate(header)
            if name.lower().startswith("path") or name.lower().endswith("_path")
        ]
        for line in lines[1:]:
            if not line.strip():
                continue
            cells = line.split("\t")
            for idx in s3_columns:
                if idx >= len(cells):
                    continue
                value = cells[idx].strip()
                if value:
                    self._assert_s3_uri_exists(value)
            for idx in sample_data_columns:
                if idx >= len(cells):
                    continue
                value = cells[idx].strip()
                if value:
                    self._assert_sample_file_exists(workset, value)

    def _stage_samples(
        self, workset: Workset, manifest_path: Path, cluster_name: str
    ) -> StageArtifacts:
        manifest_argument = self._relative_manifest_argument(manifest_path)
        reference_bucket = self._stage_reference_bucket()
        cmd = self.config.pipeline.stage_command.format(
            profile=self.config.aws.profile,
            region=self.config.aws.region,
            cluster=cluster_name,
            analysis_samples=manifest_argument,
            reference_bucket=reference_bucket,
            ssh_identity_file=self.config.pipeline.ssh_identity_file or "",
            pem=self.config.pipeline.ssh_identity_file or "",
            ssh_user=self.config.pipeline.ssh_user,
            ssh_extra_args=" ".join(
                shlex.quote(arg) for arg in self.config.pipeline.ssh_extra_args
            ),
        )
        LOGGER.info(
            "Staging samples for cluster %s with command: %s", cluster_name, cmd
        )
        result = self._run_monitored_command("stage_samples", cmd, check=True)
        artifacts = self._parse_stage_samples_output(result)
        self._stage_artifacts[workset.name] = artifacts
        LOGGER.info(
            "Recorded %d staged files for %s under %s",
            len(artifacts.staged_files),
            workset.name,
            artifacts.fsx_stage_dir,
        )
        return artifacts

    def _parse_stage_samples_output(
        self, result: subprocess.CompletedProcess
    ) -> StageArtifacts:
        outputs: List[str] = []
        if isinstance(result.stdout, (bytes, bytearray)):
            outputs.append(result.stdout.decode("utf-8", errors="ignore"))
        elif isinstance(result.stdout, str):
            outputs.append(result.stdout)
        if isinstance(result.stderr, (bytes, bytearray)):
            outputs.append(result.stderr.decode("utf-8", errors="ignore"))
        elif isinstance(result.stderr, str):
            outputs.append(result.stderr)

        combined = "\n".join(filter(None, outputs)).strip()
        if not combined:
            raise MonitorError("Stage command produced no output to parse")

        fsx_stage_dir: Optional[PurePosixPath] = None
        staged_files: List[PurePosixPath] = []
        collecting_files = False

        for raw_line in combined.splitlines():
            line = raw_line.strip()
            if not line:
                if collecting_files:
                    collecting_files = False
                continue

            if line.startswith("Remote FSx stage directory:"):
                _, value = raw_line.split(":", 1)
                path_str = value.strip()
                if not path_str:
                    raise MonitorError(
                        "Stage command did not report an FSx stage directory"
                    )
                fsx_stage_dir = PurePosixPath("/fsx") / path_str.lstrip("/")
                continue

            if line.startswith("Staged files"):
                collecting_files = True
                continue

            if collecting_files:
                if raw_line.startswith(" ") or raw_line.startswith("\t"):
                    path_candidate = line
                    if path_candidate:
                        fsx_path = PurePosixPath("/fsx") / path_candidate.lstrip("/")
                        staged_files.append(fsx_path)
                    continue
                collecting_files = False

        if fsx_stage_dir is None:
            raise MonitorError(
                "Unable to determine remote FSx stage directory from stage command output"
            )

        # Remove duplicates while preserving order
        unique_files: List[PurePosixPath] = []
        seen: Set[PurePosixPath] = set()
        for path in staged_files:
            if path not in seen:
                unique_files.append(path)
                seen.add(path)

        stage_dir_name = fsx_stage_dir.name
        timestamp = stage_dir_name.replace("remote_stage_", "")
        samples_manifest = fsx_stage_dir / f"{timestamp}_samples.tsv"
        units_manifest = fsx_stage_dir / f"{timestamp}_units.tsv"

        return StageArtifacts(
            fsx_stage_dir=fsx_stage_dir,
            staged_files=unique_files,
            samples_manifest=samples_manifest,
            units_manifest=units_manifest,
        )

    def _wait_for_cluster_ready(self, cluster_name: str) -> Optional[Dict[str, object]]:
        LOGGER.info("Waiting for cluster %s to become ready", cluster_name)
        for attempt in range(60):
            details = self._describe_cluster(cluster_name)
            if details and self._cluster_is_ready(details):
                LOGGER.debug(
                    "Cluster %s ready (checked %d times)", cluster_name, attempt + 1
                )
                return details
            LOGGER.debug("Cluster %s not ready yet (%d)", cluster_name, attempt + 1)
            time.sleep(30)
        raise MonitorError(f"Cluster {cluster_name} did not become ready in time")

    def _prepare_pipeline_workspace(
        self,
        workset: Workset,
        cluster_name: str,
        clone_args: str,
        *,
        run_clone: bool = True,
    ) -> PurePosixPath:
        if clone_args and run_clone:
            init = (self.config.pipeline.login_shell_init or "").strip()
            base = self.config.pipeline.clone_command.format(clone_args=clone_args)
            cmd = f"{init} && {base}" if init else base
            self._update_metrics(workset, {"clone_command": cmd, "clone_args": clone_args})
            result = self._run_headnode_monitored_command(
                "clone_pipeline",
                cmd,
                cluster_name=cluster_name,
                check=True,
                shell=True,  # pass as raw string to bash -lc
            )
            location = self._parse_day_clone_location(result.stdout)
            if not location and result.stderr:
                location = self._parse_day_clone_location(result.stderr)
            if not location:
                dest = self._extract_dest_from_clone_args(clone_args) or self._sanitize_name(workset.name)
                location = self._expected_pipeline_dir(dest)
                LOGGER.info(
                    "day-clone did not report Location; falling back to %s", location
                )
            LOGGER.info(
                "day-clone reported pipeline directory %s for %s",
                location,
                workset.name,
            )
            self._record_pipeline_location(workset, location)
            return location
        if clone_args:
            location = self._load_pipeline_location(workset)
            if location:
                LOGGER.info(
                    "Reusing recorded pipeline directory %s for %s",
                    location,
                    workset.name,
                )
                return location
            raise MonitorError(
                "Pipeline location unavailable for restart; rerun day-clone or remove cached state"
            )
        # No clone requested; ensure fallback dir on headnode exists
        fallback = PurePosixPath(self.config.pipeline.workdir) / workset.name
        ensure_cmd = f"mkdir -p {shlex.quote(str(fallback))}"
        self._run_headnode_command(cluster_name, ensure_cmd, check=True, shell=True)
        self._record_pipeline_location(workset, fallback)
        return fallback

    def _push_stage_files_to_pipeline(
        self,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
        manifest_path: Path,
        stage_artifacts: StageArtifacts,
    ) -> None:
        config_dir = pipeline_dir / "config"
        mkdir_cmd = f"mkdir -p {shlex.quote(str(config_dir))}"
        self._run_headnode_monitored_command(
            "push_stage_files",
            mkdir_cmd,
            cluster_name=cluster_name,
            check=True,
            shell=True,
        )
        LOGGER.info("Copying staged artifacts into %s", pipeline_dir)
        self._copy_stage_artifacts_to_pipeline(
            cluster_name, pipeline_dir, stage_artifacts, manifest_path
        )

    def _cleanup_pipeline_directory(
        self,
        workset: Workset,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
    ) -> None:
        LOGGER.info(
            "Removing pipeline directory %s from cluster %s", pipeline_dir, cluster_name
        )
        cmd = f"rm -rf {shlex.quote(str(pipeline_dir))}"
        self._run_headnode_monitored_command(
            "cleanup_pipeline",
            cmd,
            cluster_name=cluster_name,
            check=True,
            shell=True,
        )
        self._clear_pipeline_location(workset)

    def _copy_stage_artifacts_to_pipeline(
        self,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
        stage_artifacts: StageArtifacts,
        manifest_path: Path,
    ) -> None:
        sample_data_root = pipeline_dir / SAMPLE_DATA_DIRNAME
        mkdir_data = f"mkdir -p {shlex.quote(str(sample_data_root))}"
        self._run_headnode_monitored_command(
            "push_stage_files",
            mkdir_data,
            cluster_name=cluster_name,
            check=True,
            shell=True,
        )

        for staged_file in stage_artifacts.staged_files:
            try:
                relative_path = staged_file.relative_to(stage_artifacts.fsx_stage_dir)
            except ValueError:
                LOGGER.warning(
                    "Staged file %s is not within %s; skipping copy",
                    staged_file,
                    stage_artifacts.fsx_stage_dir,
                )
                continue
            destination = sample_data_root / relative_path
            copy_cmd = (
                f"mkdir -p {shlex.quote(str(destination.parent))} && "
                f"cp -p {shlex.quote(str(staged_file))} {shlex.quote(str(destination))}"
            )
            self._run_headnode_monitored_command(
                "push_stage_files",
                copy_cmd,
                cluster_name=cluster_name,
                check=True,
                shell=True,
            )

        config_dir = pipeline_dir / "config"
        samples_target = config_dir / "samples.tsv"
        units_target = config_dir / "units.tsv"

        copied_samples = False
        if stage_artifacts.samples_manifest:
            copied_samples = self._copy_file_on_headnode(
                cluster_name,
                stage_artifacts.samples_manifest,
                samples_target,
                label="push_stage_files",
                check=False,
            )
        copied_units = False
        if stage_artifacts.units_manifest:
            copied_units = self._copy_file_on_headnode(
                cluster_name,
                stage_artifacts.units_manifest,
                units_target,
                label="push_stage_files",
                check=False,
            )

        if not copied_samples:
            LOGGER.info(
                "Falling back to SCP for samples manifest from %s", manifest_path
            )
            scp_samples = self._build_scp_command(
                cluster_name, manifest_path, samples_target
            )
            self._run_monitored_command("push_stage_files", scp_samples, check=True)

        units_src = manifest_path.with_name("units.tsv")
        need_units_fallback = (
            (stage_artifacts.units_manifest is None or not copied_units)
            and units_src.exists()
        )
        if need_units_fallback:
            LOGGER.info(
                "Falling back to SCP for units manifest from %s", units_src
            )
            scp_units = self._build_scp_command(
                cluster_name, units_src, units_target
            )
            self._run_monitored_command("push_stage_files", scp_units, check=True)
        elif not copied_units and stage_artifacts.units_manifest is not None:
            LOGGER.warning(
                "Units manifest %s was not copied to %s and no fallback was available",
                stage_artifacts.units_manifest,
                units_target,
            )
        elif stage_artifacts.units_manifest is None and not units_src.exists():
            LOGGER.warning(
                "Units manifest missing: expected local fallback at %s",
                units_src,
            )

    def _copy_file_on_headnode(
        self,
        cluster_name: str,
        source: PurePosixPath,
        destination: PurePosixPath,
        *,
        label: str,
        check: bool,
    ) -> bool:
        quoted_source = shlex.quote(str(source))
        quoted_dest = shlex.quote(str(destination))
        quoted_parent = shlex.quote(str(destination.parent))
        command = (
            f"mkdir -p {quoted_parent} && cp -p {quoted_source} {quoted_dest}"
        )
        result = self._run_headnode_monitored_command(
            label,
            command,
            cluster_name=cluster_name,
            check=check,
            shell=True,
        )
        if check:
            return True
        if result.returncode != 0:
            LOGGER.debug(
                "Headnode copy command exited %s for %s -> %s",
                result.returncode,
                source,
                destination,
            )
            return False
        return True

    def _headnode_path_exists(
        self, cluster_name: str, path: PurePosixPath
    ) -> bool:
        cmd = f"test -e {shlex.quote(str(path))}"
        result = self._run_headnode_command(
            cluster_name, cmd, check=False, shell=True
        )
        return result.returncode == 0

    def _pipeline_sentinel_status(
        self, cluster_name: str, pipeline_dir: PurePosixPath
    ) -> str:
        success = pipeline_dir / PIPELINE_SUCCESS_SENTINEL
        failure = pipeline_dir / PIPELINE_FAILURE_SENTINEL
        if self._headnode_path_exists(cluster_name, success):
            return "success"
        if self._headnode_path_exists(cluster_name, failure):
            return "failure"
        return "pending"

    def _tmux_session_exists(self, cluster_name: str, session_name: str) -> bool:
        result = self._run_headnode_command(
            cluster_name,
            ["tmux", "has-session", "-t", session_name],
            check=False,
            shell=False,
        )
        return result.returncode == 0

    def _terminate_tmux_session(
        self, cluster_name: str, session_name: Optional[str]
    ) -> None:
        if not session_name:
            return
        self._run_headnode_command(
            cluster_name,
            ["tmux", "kill-session", "-t", session_name],
            check=False,
            shell=False,
        )

    def _interrupt_tmux_session(
        self, cluster_name: str, session_name: Optional[str]
    ) -> None:
        if not session_name:
            return
        self._run_headnode_command(
            cluster_name,
            ["tmux", "send-keys", "-t", session_name, "C-x"],
            check=False,
            shell=False,
        )

    def _run_pipeline(
        self,
        workset: Workset,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
        run_suffix: Optional[str],
        *,
        monitor: bool = True,
    ) -> Optional[str]:
        if not run_suffix:
            raise MonitorError(
                "Missing pipeline run suffix in daylily_work.yaml. "
                "Provide one of: dy-r, dy_r, dy, run, run_suffix, run-suffix, run_cmd."
            )

        status = self._pipeline_sentinel_status(cluster_name, pipeline_dir)
        existing_session = self._load_tmux_session(workset)
        if status == "success":
            LOGGER.info(
                "Pipeline already marked successful for %s; skipping rerun", workset.name
            )
            self._terminate_tmux_session(cluster_name, existing_session)
            self._clear_tmux_session(workset)
            self._clear_pipeline_start(workset)
            return existing_session
        if status == "failure":
            self._terminate_tmux_session(cluster_name, existing_session)
            self._clear_tmux_session(workset)
            self._clear_pipeline_start(workset)
            raise MonitorError(
                f"Pipeline previously failed for {workset.name}; investigate {PIPELINE_FAILURE_SENTINEL}"
            )

        if existing_session and not self._tmux_session_exists(
            cluster_name, existing_session
        ):
            self._clear_tmux_session(workset)
            self._clear_pipeline_start(workset)
            raise MonitorError(
                f"Recorded tmux session {existing_session} for {workset.name} is not running and no sentinel was found"
            )

        session_name = existing_session
        if not session_name:
            run_command = self.config.pipeline.run_prefix + run_suffix
            self._update_metrics(workset, {"pipeline_command": run_command.strip()})

            steps: List[str] = []
            steps.append("echo go")
            steps.append(f"cd {shlex.quote(str(pipeline_dir))}")

            init_cmd = (self.config.pipeline.login_shell_init or "").strip()
            if init_cmd:
                steps.append(init_cmd)

            steps.append(run_command)

            keepalive = (self.config.pipeline.tmux_keepalive_shell or "").strip()
            if keepalive:
                steps.append(keepalive)

            composite = " && ".join(steps)

            session_name = self._generate_tmux_session_name(workset)
            tmux_cmd = [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "bash",
                "-lc",
                composite,
            ]

            LOGGER.info(
                "Launching pipeline for %s in tmux session %s: %s",
                workset.name,
                session_name,
                run_command,
            )
            self._record_tmux_session(workset, session_name)
            self._write_pipeline_sentinel(cluster_name, pipeline_dir, "START")
            try:
                self._run_headnode_monitored_command(
                    "run_pipeline",
                    tmux_cmd,
                    cluster_name=cluster_name,
                    check=True,
                    shell=False,
                )
                self._run_headnode_command(
                    cluster_name,
                    ["tmux", "has-session", "-t", session_name],
                    check=True,
                    shell=False,
                )
                self._record_pipeline_start(workset, dt.datetime.now(dt.timezone.utc))
            except Exception:
                self._clear_tmux_session(workset)
                self._clear_pipeline_start(workset)
                raise
            finally:
                self._write_pipeline_sentinel(cluster_name, pipeline_dir, "END")

        if monitor:
            self._monitor_pipeline_session(
                workset, cluster_name, pipeline_dir, session_name
            )
        return session_name

    def _monitor_pipeline_session(
        self,
        workset: Workset,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
        session_name: str,
    ) -> None:
        poll_interval = max(10, min(60, self.config.monitor.poll_interval_seconds))
        start_time = self._load_pipeline_start(workset)
        if start_time is None:
            start_time = dt.datetime.now(dt.timezone.utc)
            self._record_pipeline_start(workset, start_time)
        timeout_minutes = self.config.pipeline.pipeline_timeout_minutes
        timeout_seconds = (timeout_minutes or 0) * 60 if timeout_minutes else None

        while True:
            status = self._pipeline_sentinel_status(cluster_name, pipeline_dir)
            if status == "success":
                LOGGER.info("Pipeline completed successfully for %s", workset.name)
                self._terminate_tmux_session(cluster_name, session_name)
                self._clear_tmux_session(workset)
                self._clear_pipeline_start(workset)
                return
            if status == "failure":
                self._terminate_tmux_session(cluster_name, session_name)
                self._clear_tmux_session(workset)
                self._clear_pipeline_start(workset)
                raise MonitorError(
                    f"Pipeline failed for {workset.name}; see {PIPELINE_FAILURE_SENTINEL}"
                )

            if not self._tmux_session_exists(cluster_name, session_name):
                self._clear_tmux_session(workset)
                self._clear_pipeline_start(workset)
                raise MonitorError(
                    f"Pipeline session {session_name} exited without a sentinel for {workset.name}"
                )

            if timeout_seconds is not None:
                elapsed = (dt.datetime.now(dt.timezone.utc) - start_time).total_seconds()
                if elapsed >= timeout_seconds:
                    LOGGER.error(
                        "Pipeline for %s exceeded timeout of %d minutes",
                        workset.name,
                        timeout_minutes,
                    )
                    status = self._pipeline_sentinel_status(cluster_name, pipeline_dir)
                    if status == "success":
                        LOGGER.info(
                            "Pipeline for %s reported success sentinel during timeout handling",
                            workset.name,
                        )
                        continue
                    if status == "failure":
                        self._terminate_tmux_session(cluster_name, session_name)
                        self._clear_tmux_session(workset)
                        self._clear_pipeline_start(workset)
                        raise MonitorError(
                            f"Pipeline failed for {workset.name}; see {PIPELINE_FAILURE_SENTINEL}"
                        )
                    self._interrupt_tmux_session(cluster_name, session_name)
                    time.sleep(5)
                    self._terminate_tmux_session(cluster_name, session_name)
                    self._clear_tmux_session(workset)
                    self._clear_pipeline_start(workset)
                    raise MonitorError(
                        f"Pipeline timed out after {timeout_minutes} minutes for {workset.name}"
                    )

            time.sleep(poll_interval)

    def _write_pipeline_sentinel(
        self,
        cluster_name: str,
        pipeline_dir: PurePosixPath,
        state: str,
    ) -> None:
        """
        Append a one-line UTC timestamp + state to a local log on the headnode.
        Idempotent and safe under re-runs.
        """
        # Quote everything carefully; run on headnode.
        log_path = str(pipeline_dir / ".daylily-monitor-sentinel.log")
        cmd = (
            f'printf "%s\\t%s\\n" "$(date -u +%FT%TZ)" {shlex.quote(state)} '
            f'>> {shlex.quote(log_path)}'
        )
        self._run_headnode_monitored_command(
            "pipeline_sentinel",
            cmd,
            cluster_name=cluster_name,
            check=True,
            shell=True,
        )

    def _export_results(
        self,
        workset: Workset,
        cluster_name: str,
        target_uri: str,
        pipeline_dir: PurePosixPath,
    ) -> None:
        output_dir = self._local_state_dir(workset)
        profile_value = self.config.aws.profile or ""
        command = self.config.pipeline.export_command.format(
            cluster=shlex.quote(cluster_name),
            target_uri=shlex.quote(target_uri),
            region=shlex.quote(self.config.aws.region),
            profile=shlex.quote(profile_value) if profile_value else "",
            output_dir=shlex.quote(str(output_dir)),
            workdir_name=self._resolve_workdir_name(workset),
            workset_dir=shlex.quote(str(pipeline_dir)),
            pipeline_dir=shlex.quote(str(pipeline_dir)),
            workset=shlex.quote(workset.name),
        )
        LOGGER.info("Exporting pipeline results for %s to %s", workset.name, target_uri)
        self._run_monitored_command(
            "export_results", command, check=True, shell=True
        )

        status_path = output_dir / FSX_EXPORT_STATUS_FILENAME
        if not status_path.exists():
            raise MonitorError(
                f"Export command for {workset.name} did not produce {FSX_EXPORT_STATUS_FILENAME}"
            )
        try:
            status_data = yaml.safe_load(status_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise MonitorError(
                f"Unable to parse export status for {workset.name}: {exc}"
            ) from exc
        if not isinstance(status_data, dict) or "fsx_export" not in status_data:
            raise MonitorError(
                f"Export status for {workset.name} missing fsx_export block"
            )
        details = status_data.get("fsx_export")
        if not isinstance(details, dict):
            raise MonitorError(
                f"Export status for {workset.name} has unexpected format"
            )
        status = str(details.get("status", "")).lower()
        s3_uri = details.get("s3_uri")
        if status != "success":
            raise MonitorError(
                f"Export command reported failure for {workset.name}: status={status or 'unknown'}"
            )
        LOGGER.info(
            "Export completed for %s; results available at %s", workset.name, s3_uri
        )
        if self.config.cluster.auto_teardown:
            self._maybe_shutdown_cluster(cluster_name)

    # ------------------------------------------------------------------
    # Cluster helpers
    # ------------------------------------------------------------------
    def _cluster_has_tmux_sessions(self, cluster_name: str) -> bool:
        result = self._run_headnode_command(
            cluster_name, ["tmux", "list-sessions"], check=False, shell=False
        )
        if result.returncode != 0:
            return False
        output = result.stdout
        if isinstance(output, (bytes, bytearray)):
            text = output.decode("utf-8", errors="ignore")
        else:
            text = str(output)
        return bool(text.strip())

    def _cluster_job_count(self, cluster_name: str) -> Optional[int]:
        cmd = "squeue | wc -l"
        result = self._run_headnode_command(
            cluster_name, ["bash", "-lc", cmd], check=False, shell=False
        )
        if result.returncode != 0:
            LOGGER.warning(
                "Unable to determine job count on %s (exit %s)",
                cluster_name,
                result.returncode,
            )
            return None
        output = result.stdout
        if isinstance(output, (bytes, bytearray)):
            text = output.decode("utf-8", errors="ignore")
        else:
            text = str(output)
        try:
            return int(text.strip() or "0")
        except ValueError:
            LOGGER.warning(
                "Unexpected job count output from %s: %s", cluster_name, text.strip()
            )
            return None

    def _shutdown_cluster(self, cluster_name: str) -> None:
        LOGGER.info("Shutting down cluster %s", cluster_name)
        cmd = [
            "pcluster",
            "delete-cluster",
            "--region",
            self.config.aws.region,
            "-n",
            cluster_name,
        ]
        self._run_monitored_command(
            "delete_cluster", cmd, check=True, env=self._pcluster_env()
        )

    def _maybe_shutdown_cluster(self, cluster_name: str) -> None:
        if not self.config.cluster.auto_teardown:
            return
        if self._cluster_has_tmux_sessions(cluster_name):
            LOGGER.info(
                "Skipping shutdown of %s: tmux sessions remain active", cluster_name
            )
            self._clear_cluster_idle(cluster_name)
            return
        job_count = self._cluster_job_count(cluster_name)
        if job_count is None:
            LOGGER.info(
                "Skipping shutdown of %s: unable to determine job queue", cluster_name
            )
            self._clear_cluster_idle(cluster_name)
            return
        if job_count > 1:
            LOGGER.info(
                "Skipping shutdown of %s: %d jobs still in queue", cluster_name, job_count - 1
            )
            self._clear_cluster_idle(cluster_name)
            return

        idle_marker = self._cluster_idle_marker(cluster_name)
        now = dt.datetime.now(dt.timezone.utc)
        if idle_marker.exists():
            text = idle_marker.read_text(encoding="utf-8").strip()
            with contextlib.suppress(ValueError):
                recorded = dt.datetime.fromisoformat(text)
                elapsed = (now - recorded).total_seconds()
                if elapsed >= 600:
                    LOGGER.info(
                        "Cluster %s idle for %.0f seconds; initiating shutdown",
                        cluster_name,
                        elapsed,
                    )
                    self._shutdown_cluster(cluster_name)
                    self._clear_cluster_idle(cluster_name)
                    return
                LOGGER.info(
                    "Cluster %s idle for %.0f seconds; waiting for 600 seconds",
                    cluster_name,
                    elapsed,
                )
                return
        idle_marker.write_text(now.isoformat(), encoding="utf-8")
        LOGGER.info(
            "Cluster %s is idle; will shutdown after 600 seconds if still idle",
            cluster_name,
        )

    def _ensure_cluster(self, work_yaml: Dict[str, object]) -> str:
        if self.config.cluster.reuse_cluster_name:
            return self.config.cluster.reuse_cluster_name
        existing = self._find_existing_cluster()
        if existing:
            return existing
        return self._create_cluster(work_yaml)

    def _pcluster_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        if self.config.aws.profile:
            env["AWS_PROFILE"] = self.config.aws.profile
        return env

    def _load_pcluster_json(self, raw: bytes) -> Optional[Any]:
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            return None
        brace_positions = [pos for pos in (text.find("{"), text.find("[")) if pos != -1]
        if brace_positions:
            text = text[min(brace_positions):]
        try:
            result: Any = json.loads(text)
            return result
        except json.JSONDecodeError as exc:
            LOGGER.debug("Failed to decode pcluster output as JSON: %s", exc)
            return None

    def _describe_cluster(self, cluster_name: str) -> Optional[Dict[str, object]]:
        cmd = ["pcluster", "describe-cluster", "--region", self.config.aws.region, "-n", cluster_name]
        result = self._run_command(cmd, check=False, env=self._pcluster_env())
        if result.returncode != 0:
            LOGGER.debug(
                "Unable to describe cluster %s (exit %s): %s",
                cluster_name,
                result.returncode,
                result.stderr.decode(errors="ignore"),
            )
            return None
        payload = self._load_pcluster_json(result.stdout)
        if isinstance(payload, dict):
            return payload
        LOGGER.debug("Unexpected describe-cluster output for %s", cluster_name)
        return None

    def _cluster_is_ready(self, details: Dict[str, object]) -> bool:
        cluster_status = str(details.get("clusterStatus", "")).upper()
        compute_status = str(details.get("computeFleetStatus", "")).upper()
        if cluster_status not in READY_CLUSTER_STATUSES:
            return False
        if compute_status and compute_status not in READY_COMPUTE_FLEET_STATUSES:
            return False
        return True

    def _extract_cluster_zone(self, details: Dict[str, object]) -> Optional[str]:
        head_node = details.get("headNode")
        if isinstance(head_node, dict):
            zone = head_node.get("availabilityZone") or head_node.get("AvailabilityZone")
            if isinstance(zone, str):
                return zone
        return None

    def _find_existing_cluster(self) -> Optional[str]:
        LOGGER.debug("Checking for existing clusters in %s", self.config.aws.region)
        cmd = ["pcluster", "list-clusters", "--region", self.config.aws.region]
        result = self._run_command(cmd, check=False, env=self._pcluster_env())
        if result.returncode != 0:
            LOGGER.debug(
                "Unable to list clusters (exit %s): %s",
                result.returncode,
                result.stderr.decode(errors="ignore"),
            )
            return None
        payload = self._load_pcluster_json(result.stdout)
        if not isinstance(payload, dict):
            LOGGER.debug("Unexpected list-clusters output: %s", result.stdout.decode(errors="ignore"))
            return None
        clusters = payload.get("clusters")
        if not isinstance(clusters, list):
            return None
        preferred_zone = self.config.cluster.preferred_availability_zone
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            name_raw = cluster.get("clusterName")
            if not name_raw or not isinstance(name_raw, str):
                continue
            name: str = name_raw
            details = self._describe_cluster(name)
            if not details:
                continue
            if preferred_zone:
                cluster_zone = self._extract_cluster_zone(details)
                if cluster_zone and cluster_zone != preferred_zone:
                    LOGGER.debug(
                        "Skipping cluster %s due to availability zone mismatch (%s != %s)",
                        name,
                        cluster_zone,
                        preferred_zone,
                    )
                    continue
                if not cluster_zone:
                    LOGGER.debug(
                        "Cluster %s missing availability zone information; unable to enforce preference",
                        name,
                    )
            if self._cluster_is_ready(details):
                return name
        return None

    def _create_cluster(self, work_yaml: Dict[str, object]) -> str:
        cluster_name_raw = work_yaml.get("cluster_name")
        cluster_name: str = str(cluster_name_raw) if cluster_name_raw else f"daylily-{int(time.time())}"
        LOGGER.info("Creating new ephemeral cluster %s", cluster_name)
        cmd: List[str] = ["./bin/daylily-create-ephemeral-cluster", "--cluster-name", cluster_name]
        if self.config.cluster.template_path:
            cmd.extend(["--config", self.config.cluster.template_path])
        env = os.environ.copy()
        contact_email = self.config.cluster.contact_email or "you@email.com"
        env["DAY_CONTACT_EMAIL"] = contact_email
        env.pop("DAY_DISABLE_AUTO_SELECT", None)
        result = self._run_command(cmd, check=True, env=env)
        LOGGER.debug(
            "Cluster creation stdout: %s", result.stdout.decode(errors="ignore")
        )
        return cluster_name

    # ------------------------------------------------------------------
    # File and S3 helpers
    # ------------------------------------------------------------------
    
    def _assert_s3_uri_exists(self, uri: str) -> None:
        """Verify that s3://bucket/key exists."""
        if not uri.startswith("s3://"):
            raise MonitorError(f"Invalid S3 URI: {uri}")
        remainder = uri[5:]
        parts = remainder.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise MonitorError(f"Invalid S3 URI: {uri}")
        bucket, key = parts
        try:
            self._s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            raise MonitorError(f"Referenced S3 object not found: {uri}") from exc

    def _assert_sample_file_exists(self, workset: Workset, relative_path: str) -> None:
        """Verify that a sample_data file exists inside the workset prefix."""
        key = f"{workset.prefix}{SAMPLE_DATA_DIRNAME}/{relative_path.lstrip('/')}"
        try:
            self._s3.head_object(Bucket=self.config.monitor.bucket, Key=key)
        except ClientError as exc:
            raise MonitorError(f"Sample data file missing for {workset.name}: {relative_path}") from exc
    def _read_required_object(self, workset_prefix: str, filename: str) -> bytes:
        bucket = self.config.monitor.bucket
        key = f"{workset_prefix}{filename}"
        try:
            response = self._s3.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            raise MonitorError(
                f"Missing required file {filename} in {workset_prefix}: {exc}"
            ) from exc
        content: bytes = response["Body"].read()
        return content

    def _write_sentinel(self, workset: Workset, sentinel_name: str, value: str) -> None:
        bucket = self.config.monitor.bucket
        key = f"{workset.prefix}{sentinel_name}"
        body = value.encode("utf-8")
        LOGGER.debug("Writing sentinel %s for %s", sentinel_name, workset.name)
        if self.dry_run:
            return
        self._s3.put_object(Bucket=bucket, Key=key, Body=body)
        self._record_terminal_metrics(workset, sentinel_name, value)

        # Also update DynamoDB state if integration layer is available
        self._sync_sentinel_to_dynamodb(workset.name, sentinel_name, value)

    def _sync_sentinel_to_dynamodb(
        self, workset_id: str, sentinel_name: str, value: str
    ) -> None:
        """Sync sentinel state change to DynamoDB.

        Args:
            workset_id: Workset identifier
            sentinel_name: Name of sentinel file written
            value: Timestamp/content of sentinel
        """
        if not self.state_db:
            return

        # Map sentinel names to DynamoDB states
        sentinel_to_state = {
            SENTINEL_FILES["ready"]: "ready",
            SENTINEL_FILES["in_progress"]: "in_progress",
            SENTINEL_FILES["error"]: "error",
            SENTINEL_FILES["complete"]: "complete",
            SENTINEL_FILES["ignore"]: "ignored",
        }

        new_state = sentinel_to_state.get(sentinel_name)
        if not new_state:
            return

        try:
            from daylib.workset_state_db import WorksetState
            ws_state = WorksetState(new_state)
            self.state_db.update_state(
                workset_id=workset_id,
                new_state=ws_state,
                reason=f"Sentinel {sentinel_name} written by monitor",
            )
            LOGGER.debug("Synced sentinel %s to DynamoDB state %s", sentinel_name, new_state)
        except Exception as e:
            LOGGER.warning("Failed to sync sentinel to DynamoDB for %s: %s", workset_id, str(e))

    def _delete_sentinel(self, workset: Workset, sentinel_name: str) -> None:
        bucket = self.config.monitor.bucket
        key = f"{workset.prefix}{sentinel_name}"
        LOGGER.debug("Deleting sentinel %s for %s", sentinel_name, workset.name)
        if self.dry_run:
            return
        self._s3.delete_object(Bucket=bucket, Key=key)

    def _write_temp_file(self, workset: Workset, filename: str, data: bytes) -> Path:
        temp_dir = Path("/tmp") / f"daylily-workset-{workset.name}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        path = temp_dir / filename
        path.write_bytes(data)
        return path

    def _local_stage_root(self) -> Optional[Path]:
        root = self.config.pipeline.local_stage_root
        if not root:
            return None
        path = Path(root).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _copy_manifest_to_local(self, workset: Workset, manifest_path: Path) -> Path:
        """Optional mirror of stage_samples.tsv to a local cache (for audit/inspection)."""
        local_root = self._local_stage_root()
        if not local_root:
            return manifest_path
        destination_dir = local_root / workset.name
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / manifest_path.name
        shutil.copy2(manifest_path, destination_path)
        LOGGER.info("Copied stage manifest for %s to %s", workset.name, destination_path)
        return destination_path

    def _relative_manifest_argument(self, manifest_path: Path) -> str:
        """Prefer a relative path when possible, otherwise absolute."""
        try:
            return str(manifest_path.relative_to(Path.cwd()))
        except ValueError:
            return str(manifest_path)

    def _stage_reference_bucket(self) -> str:
        """
        Return the S3 reference bucket to pass to the staging command.
        Uses pipeline.reference_bucket if set; otherwise defaults to the monitor's bucket.
        Always ends with a trailing '/'.
        """
        bucket = self.config.pipeline.reference_bucket
        if not bucket:
            bucket = f"s3://{self.config.monitor.bucket}"
        if not bucket.endswith("/"):
            bucket += "/"
        return bucket

    def _read_object_text(self, bucket: str, key: str) -> str:
        response = self._s3.get_object(Bucket=bucket, Key=key)
        content: str = response["Body"].read().decode("utf-8")
        return content

    def _should_process(self, workset: Workset) -> bool:
        if not self._process_directories:
            return True
        return workset.name in self._process_directories

    def _generate_report_rows(self, worksets: Sequence[Workset]) -> List[WorksetReportRow]:
        rows: List[WorksetReportRow] = []
        for workset in worksets:
            if not self._should_process(workset):
                continue
            row = self._summarize_workset(workset)
            try:
                row.metrics = self._gather_workset_metrics(workset, row)
            except Exception:
                LOGGER.debug("Failed to gather metrics for %s", workset.name, exc_info=True)
            if workset.is_archived:
                row.display_state = f"{row.state_text} (archived)"
            rows.append(row)
        rows.sort(key=self._report_sort_key)
        return rows

    def _summarize_workset(self, workset: Workset) -> WorksetReportRow:
        sentinels = workset.sentinels

        def sentinel_parts(name: str) -> Tuple[Optional[str], Optional[str]]:
            raw = sentinels.get(name)
            if not raw:
                return None, None
            text = raw.strip()
            if not text:
                return None, None
            if "\t" in text:
                timestamp, detail = text.split("\t", 1)
            else:
                timestamp, detail = text, None
            return timestamp or None, detail or None

        sentinel_cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

        def cached_sentinel_parts(name: str) -> Tuple[Optional[str], Optional[str]]:
            if name not in sentinel_cache:
                sentinel_cache[name] = sentinel_parts(name)
            return sentinel_cache[name]

        ignore_ts, ignore_detail = cached_sentinel_parts(SENTINEL_FILES["ignore"])
        if ignore_ts:
            other_state: Optional[str] = None
            for sentinel_name, state_name in [
                ("error", "error"),
                ("complete", "complete"),
                ("in_progress", "in-progress"),
                ("lock", "locked"),
                ("ready", "ready"),
            ]:
                other_ts, _ = cached_sentinel_parts(SENTINEL_FILES[sentinel_name])
                if other_ts:
                    other_state = state_name
                    break
            display_state = "ignored"
            if other_state:
                display_state = f"ignored ({other_state})"
            return WorksetReportRow(
                workset.name,
                "ignored",
                ignore_ts,
                ignore_detail,
                workset.has_required_files,
                display_state=display_state,
            )

        error_ts, error_detail = cached_sentinel_parts(SENTINEL_FILES["error"])
        if error_ts:
            return WorksetReportRow(
                workset.name, "error", error_ts, error_detail, workset.has_required_files
            )

        complete_ts, _ = cached_sentinel_parts(SENTINEL_FILES["complete"])
        if complete_ts:
            return WorksetReportRow(
                workset.name, "complete", complete_ts, None, workset.has_required_files
            )

        in_progress_ts, _ = cached_sentinel_parts(SENTINEL_FILES["in_progress"])
        if in_progress_ts:
            return WorksetReportRow(
                workset.name, "in-progress", in_progress_ts, None, workset.has_required_files
            )

        lock_ts, _ = cached_sentinel_parts(SENTINEL_FILES["lock"])
        if lock_ts:
            return WorksetReportRow(
                workset.name, "locked", lock_ts, None, workset.has_required_files
            )

        ready_ts, _ = cached_sentinel_parts(SENTINEL_FILES["ready"])
        if ready_ts:
            return WorksetReportRow(
                workset.name, "ready", ready_ts, None, workset.has_required_files
            )

        return WorksetReportRow(workset.name, "unknown", None, None, workset.has_required_files)

    def _report_sort_key(self, row: WorksetReportRow) -> Tuple[int, str]:
        priority = STATE_PRIORITIES.get(row.state, max(STATE_PRIORITIES.values()) + 1)
        return priority, row.name

    def _render_term_report(
        self, rows: Sequence[WorksetReportRow], *, min_details: bool
    ) -> None:
        if not rows:
            print("No worksets matched the selection.")
            return
        headers, table_rows = self._prepare_report_table(rows, min_details=min_details)
        col_widths: List[int] = []
        for idx, header in enumerate(headers):
            values = [header] + [row[idx] for row in table_rows]
            col_widths.append(max(len(value) for value in values))

        header_line = "  ".join(
            f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers))
        )
        print(header_line)
        print("-" * len(header_line))

        state_index = headers.index("State")
        valid_index = headers.index("Valid")
        reset = "\033[0m"
        for source_row, data_row in zip(rows, table_rows):
            formatted_parts: List[str] = []
            for idx, value in enumerate(data_row):
                text = value
                padding = f"{{:<{col_widths[idx]}}}".format
                if idx == state_index:
                    color = STATE_COLORS.get(source_row.state, STATE_COLORS["unknown"])
                    text = f"{color}{padding(value)}{reset}"
                elif idx == valid_index and not source_row.has_required_files:
                    text = f"\033[31m{padding(value)}{reset}"
                else:
                    text = padding(value)
                formatted_parts.append(text)
            print("  ".join(formatted_parts))

    def _write_delimited_report(
        self,
        rows: Sequence[WorksetReportRow],
        path: Path,
        delimiter: str,
        *,
        min_details: bool,
    ) -> None:
        headers, table_rows = self._prepare_report_table(rows, min_details=min_details)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter=delimiter)
            writer.writerow(headers)
            for data_row in table_rows:
                writer.writerow(data_row)

    def report(
        self,
        target: str,
        *,
        min_details: bool = False,
        include_archive: bool = False,
    ) -> None:
        worksets = list(self._discover_worksets(include_archive=include_archive))
        rows = self._generate_report_rows(worksets)
        if self._process_directories:
            found = {row.name for row in rows}
            missing = sorted(self._process_directories - found)
            for name in missing:
                LOGGER.warning("Requested workset %s was not found", name)

        if target.lower() == "term":
            self._render_term_report(rows, min_details=min_details)
            return

        # Buffer CSV/TSV once so we can write to S3 or local
        def _serialize(rows: Sequence[WorksetReportRow], delim: str) -> bytes:
            from io import StringIO

            headers, table_rows = self._prepare_report_table(
                rows, min_details=min_details
            )
            buf = StringIO()
            w = csv.writer(buf, delimiter=delim)
            w.writerow(headers)
            for data_row in table_rows:
                w.writerow(data_row)
            return buf.getvalue().encode("utf-8")

        if target.startswith("s3://"):
            delim = "\t" if target.lower().endswith(".tsv") else ","
            body = _serialize(rows, delim)
            bucket, key = target[5:].split("/", 1)
            if self.dry_run:
                print(f"[DRY-RUN] put_object s3://{bucket}/{key} ({len(body)} bytes)")
            else:
                self._s3.put_object(Bucket=bucket, Key=key, Body=body)
            LOGGER.info("Wrote report with %d entries to %s", len(rows), target)
            return

        # local file
        path = Path(target)
        suffix = path.suffix.lower()
        delim = "\t" if suffix == ".tsv" else ","
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        self._write_delimited_report(rows, path, delim, min_details=min_details)
        LOGGER.info("Wrote report with %d entries to %s", len(rows), path)

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------
    def _run_monitored_command(
        self,
        command_label: str,
        command: Sequence[str] | str,
        *,
        check: bool,
        cwd: Optional[Path] = None,
        shell: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        if isinstance(command, (str, bytes)) and not shell:
            cmd_display = command
        else:
            cmd_display = " ".join(command) if not isinstance(command, str) else command
        try:
            return self._run_command(
                command, check=check, cwd=cwd, shell=shell, env=env
            )
        except MonitorError as exc:
            raise CommandFailedError(command_label, str(cmd_display)) from exc

    def _run_command(
        self,
        command: Sequence[str] | str,
        *,
        check: bool,
        cwd: Optional[Path] = None,
        shell: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        if isinstance(command, (str, bytes)) and not shell:
            cmd_display = command
        else:
            cmd_display = " ".join(command) if not isinstance(command, str) else command
        LOGGER.debug("Executing command: %s", cmd_display)

        action = "DRY-RUN" if self.dry_run else "EXEC"
        if self.dry_run or self.debug:
            print(f"[{action}] {cmd_display}")

        if self.dry_run:
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=b"", stderr=b"")

        run_command = command
        run_shell = shell
        if isinstance(command, str) and not shell:
            run_command = shlex.split(command)
        result = subprocess.run(
            run_command,
            check=False,
            cwd=cwd,
            shell=run_shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        if check and result.returncode != 0:
            LOGGER.error(
                "Command failed (%s): %s",
                result.returncode,
                result.stderr.decode(errors="ignore"),
            )
            raise MonitorError(f"Command failed: {cmd_display}")
        return result

    def _ssh_identity(self) -> Optional[str]:
        identity = self.config.pipeline.ssh_identity_file
        if not identity:
            return None
        return str(Path(identity).expanduser())

    def _ssh_user(self) -> str:
        return self.config.pipeline.ssh_user or "ubuntu"

    def _ssh_options(self) -> List[str]:
        options = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]
        if self.config.pipeline.ssh_extra_args:
            options.extend(self.config.pipeline.ssh_extra_args)
        return options

    def _headnode_ip(self, cluster_name: str) -> str:
        cached = self._headnode_ips.get(cluster_name)
        if cached:
            return cached
        cmd = ["pcluster", "describe-cluster-instances", "--region", self.config.aws.region, "-n", cluster_name]
        result = self._run_command(cmd, check=True, env=self._pcluster_env())
        payload = self._load_pcluster_json(result.stdout)
        if isinstance(payload, dict):
            instances = payload.get("instances")
            if isinstance(instances, list):
                for instance in instances:
                    if not isinstance(instance, dict):
                        continue
                    node_type = instance.get("nodeType") or instance.get("NodeType")
                    if isinstance(node_type, str) and node_type.lower() == "headnode":
                        ip = instance.get("publicIpAddress") or instance.get("PublicIpAddress")
                        if isinstance(ip, str) and ip:
                            self._headnode_ips[cluster_name] = ip
                            return ip
        raise MonitorError(f"Unable to determine head node address for {cluster_name}")

    def _build_remote_command(
        self,
        command: Sequence[str] | str,
        *,
        cwd: Optional[str] = None,
        shell: bool = False,
    ) -> str:
        if isinstance(command, (list, tuple)):
            command_str = " ".join(shlex.quote(str(part)) for part in command)
        else:
            # At this point, command is str (not Sequence[str])
            cmd_str = cast(str, command)
            command_str = cmd_str if shell else " ".join(shlex.quote(part) for part in shlex.split(cmd_str))
        if cwd:
            command_str = f"cd {shlex.quote(cwd)} && {command_str}"
        return f"bash -lc {shlex.quote(command_str)}"


    def _build_ssh_command(
        self,
        cluster_name: str,
        command: Sequence[str] | str,
        *,
        cwd: Optional[str] = None,
        shell: bool = False,
    ) -> List[str]:
        remote_command = self._build_remote_command(command, cwd=cwd, shell=shell)
        headnode = self._headnode_ip(cluster_name)
        ssh_cmd: List[str] = ["ssh"]
        identity = self._ssh_identity()
        if identity:
            ssh_cmd.extend(["-i", identity])
        ssh_cmd.extend(self._ssh_options())
        ssh_cmd.append(f"{self._ssh_user()}@{headnode}")
        ssh_cmd.append(remote_command)
        return ssh_cmd

    def _build_scp_command(
        self,
        cluster_name: str,
        local_path: Path,
        remote_path: PurePosixPath,
    ) -> List[str]:
        headnode = self._headnode_ip(cluster_name)
        scp_cmd: List[str] = ["scp"]
        identity = self._ssh_identity()
        if identity:
            scp_cmd.extend(["-i", identity])
        scp_cmd.extend(self._ssh_options())
        remote_target = f"{self._ssh_user()}@{headnode}:{remote_path}"
        scp_cmd.extend([str(local_path), remote_target])
        return scp_cmd

    def _run_headnode_command(
        self,
        cluster_name: str,
        command: Sequence[str] | str,
        *,
        check: bool,
        cwd: Optional[str] = None,
        shell: bool = False,
    ) -> subprocess.CompletedProcess:
        ssh_cmd = self._build_ssh_command(cluster_name, command, cwd=cwd, shell=shell)
        return self._run_command(ssh_cmd, check=check)

    def _run_headnode_monitored_command(
        self,
        command_label: str,
        command: Sequence[str] | str,
        *,
        cluster_name: str,
        check: bool,
        cwd: Optional[str] = None,
        shell: bool = False,
    ) -> subprocess.CompletedProcess:
        ssh_cmd = self._build_ssh_command(cluster_name, command, cwd=cwd, shell=shell)
        return self._run_monitored_command(command_label, ssh_cmd, check=check)

    def _yaml_get_str(self, data: Dict[str, object], keys: Sequence[str]) -> Optional[str]:
        """Return first non-empty string for any of the given keys. If list, join; if dict, use suffix/args/cmd/command."""
        for k in keys:
            if k not in data:
                continue
            v = data[k]
            if v is None:
                continue
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, (list, tuple)):
                parts = [str(x).strip() for x in v if str(x).strip()]
                if parts:
                    return " ".join(parts)
            if isinstance(v, dict):
                for candidate in ("suffix", "args", "cmd", "command"):
                    val = v.get(candidate)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        return None

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _refresh_session(self) -> None:
        LOGGER.debug(
            "Validating STS caller identity for profile %s", self.config.aws.profile
        )
        try:
            identity = self._sts.get_caller_identity()
            LOGGER.info("Assumed identity: %s", identity.get("Arn"))
        except ClientError as exc:
            LOGGER.warning("Unable to validate AWS credentials: %s", exc)


def configure_logging(verbose: bool) -> None:
    """Configure module-wide logging for monitor helpers."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
