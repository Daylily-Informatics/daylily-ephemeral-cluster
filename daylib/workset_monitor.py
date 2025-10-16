"""Tools for monitoring S3 workset directories and orchestrating pipeline runs.

This module provides the :class:`S3WorksetMonitor` class which encapsulates the logic
for polling a bucket/prefix for new worksets, acquiring a cooperative lock via
sentinel files, running staging/cluster/pipeline commands, and updating
completion sentinels.  The implementation focuses on observability, retries, and
clear separation between S3 interactions and workflow execution so the monitor
can be extended or unit-tested easily.

The monitor expects the following directory structure::

    s3://<bucket>/<root_prefix>/
        ready/
            workset_YYYYmmddHHMMSS/
                daylily.ready
                ... other sentinel files ...
        in_flight/
        complete/
        error/
        ignore/

Within each workset directory the monitor looks for the files described in the
module level documentation.  See :func:`load_workset_configuration` for the
exact keys expected in ``daylily_work.yaml``.
"""

from __future__ import annotations

import csv
import dataclasses
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

import boto3
import botocore
import yaml

LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = REPO_ROOT / "bin"


class MonitorError(Exception):
    """Base exception for monitor failures."""


@dataclass(frozen=True)
class S3Location:
    """Simple representation of an S3 location."""

    bucket: str
    key: str

    @classmethod
    def parse(cls, uri: str) -> "S3Location":
        if not uri.startswith("s3://"):
            raise ValueError(f"Not a valid S3 URI: {uri}")
        without_scheme = uri[5:]
        bucket, _, key = without_scheme.partition("/")
        if not bucket or not key:
            raise ValueError(f"Incomplete S3 URI: {uri}")
        return cls(bucket=bucket, key=key)

    def join(self, *parts: str) -> "S3Location":
        new_key = "/".join(p.strip("/") for p in (self.key, *parts) if p)
        return S3Location(bucket=self.bucket, key=new_key)

    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


@dataclass
class StageConfig:
    """Configuration for staging sample data onto the head node."""

    samples_tsv: str = "stage_samples.tsv"
    units_tsv: Optional[str] = None
    pem_key: Optional[str] = None
    extra_args: Sequence[str] = dataclasses.field(default_factory=list)


@dataclass
class ClusterConfig:
    """Configuration for the ephemeral cluster lifecycle."""

    name: str
    template: Optional[str] = None
    create_args: Sequence[str] = dataclasses.field(default_factory=list)
    destroy_on_completion: bool = True
    allow_existing: bool = False


@dataclass
class PipelineConfig:
    """Configuration for running a pipeline once staging is complete."""

    day_clone: Sequence[str] = dataclasses.field(default_factory=list)
    run_directory: Optional[str] = None
    samples_config_path: str = "config/samples.tsv"
    units_config_path: str = "config/units.tsv"
    dy_a_args: Sequence[str] = dataclasses.field(default_factory=lambda: ["slurm", "hg38"])
    dy_r_command: str = ""
    environment: Dict[str, str] = dataclasses.field(default_factory=dict)


@dataclass
class WorksetConfig:
    """Aggregated configuration derived from ``daylily_work.yaml``."""

    aws_profile: str
    aws_region: str
    stage: StageConfig
    cluster: ClusterConfig
    pipeline: PipelineConfig


SENTINEL_READY = "daylily.ready"
SENTINEL_LOCK = "daylily.lock"
SENTINEL_IN_PROGRESS = "daylily.in_progress"
SENTINEL_ERROR = "daylily.error"
SENTINEL_COMPLETE = "daylily.complete"
SENTINEL_IGNORE = "daylily.ignore"

SENTINEL_NAMES = {
    SENTINEL_READY,
    SENTINEL_LOCK,
    SENTINEL_IN_PROGRESS,
    SENTINEL_ERROR,
    SENTINEL_COMPLETE,
    SENTINEL_IGNORE,
}


def load_workset_configuration(workset_root: Path) -> WorksetConfig:
    """Load and validate ``daylily_work.yaml`` from ``workset_root``."""

    config_path = workset_root / "daylily_work.yaml"
    if not config_path.exists():
        raise MonitorError(f"Missing daylily_work.yaml in {workset_root}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    try:
        aws = raw_config["aws"]
        stage_cfg = raw_config.get("stage", {})
        cluster_cfg = raw_config["cluster"]
        pipeline_cfg = raw_config["pipeline"]
    except KeyError as err:  # pragma: no cover - defensive programming
        raise MonitorError(f"Missing required configuration key: {err}") from err

    stage = StageConfig(
        samples_tsv=stage_cfg.get("samples_tsv", "stage_samples.tsv"),
        units_tsv=stage_cfg.get("units_tsv"),
        pem_key=stage_cfg.get("pem_key"),
        extra_args=tuple(stage_cfg.get("extra_args", [])),
    )

    cluster = ClusterConfig(
        name=cluster_cfg["name"],
        template=cluster_cfg.get("template"),
        create_args=tuple(cluster_cfg.get("create_args", [])),
        destroy_on_completion=cluster_cfg.get("destroy_on_completion", True),
        allow_existing=cluster_cfg.get("allow_existing", False),
    )

    pipeline = PipelineConfig(
        day_clone=tuple(pipeline_cfg.get("day_clone", [])),
        run_directory=pipeline_cfg.get("run_directory"),
        samples_config_path=pipeline_cfg.get("samples_config_path", "config/samples.tsv"),
        units_config_path=pipeline_cfg.get("units_config_path", "config/units.tsv"),
        dy_a_args=tuple(pipeline_cfg.get("dy_a_args", ["slurm", "hg38"])),
        dy_r_command=pipeline_cfg.get("dy_r_command", ""),
        environment=dict(pipeline_cfg.get("environment", {})),
    )

    return WorksetConfig(
        aws_profile=aws["profile"],
        aws_region=aws["region"],
        stage=stage,
        cluster=cluster,
        pipeline=pipeline,
    )


def list_s3_common_prefixes(
    client: botocore.client.BaseClient,
    bucket: str,
    prefix: str,
) -> Iterable[str]:
    """Yield child prefixes underneath ``prefix`` (non-recursive)."""

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for common in page.get("CommonPrefixes", []):
            child_prefix = common.get("Prefix")
            if child_prefix:
                yield child_prefix


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class S3WorksetMonitor:
    """Monitor an S3 prefix for Daylily worksets and process them sequentially."""

    def __init__(
        self,
        *,
        root: S3Location,
        aws_profile: Optional[str],
        aws_region: Optional[str],
        poll_seconds: int = 60,
        local_root: Optional[Path] = None,
    ) -> None:
        session = boto3.session.Session(profile_name=aws_profile, region_name=aws_region)
        self._s3 = session.client("s3")
        self._root = root
        self._poll_seconds = poll_seconds
        self._local_root = local_root or Path(tempfile.gettempdir()) / "daylily-worksets"
        self._local_root.mkdir(parents=True, exist_ok=True)

    def run_forever(self) -> None:
        LOGGER.info("Starting Daylily workset monitor for %s", self._root.uri())
        try:
            while True:
                self.process_ready_once()
                time.sleep(self._poll_seconds)
        except KeyboardInterrupt:  # pragma: no cover - manual interruption
            LOGGER.info("Monitor interrupted, shutting down")

    def process_ready_once(self) -> None:
        ready_prefix = self._root.join("ready").key + "/"
        for workset_prefix in list_s3_common_prefixes(self._s3, self._root.bucket, ready_prefix):
            LOGGER.debug("Found candidate workset prefix %s", workset_prefix)
            try:
                self._handle_workset(ready_prefix, workset_prefix)
            except Exception as exc:  # noqa: BLE001 - log & continue
                LOGGER.exception("Failed to process workset %s: %s", workset_prefix, exc)

    # -- sentinel management -------------------------------------------------
    def _list_sentinels(self, bucket: str, prefix: str) -> Dict[str, datetime]:
        response = self._s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        sentinels: Dict[str, datetime] = {}
        for obj in response.get("Contents", []):
            name = obj["Key"].split("/")[-1]
            if name in SENTINEL_NAMES:
                sentinels[name] = obj["LastModified"].replace(tzinfo=timezone.utc)
        return sentinels

    def _write_sentinel(self, location: S3Location, name: str) -> None:
        LOGGER.debug("Writing sentinel %s to %s", name, location.uri())
        self._s3.put_object(
            Bucket=location.bucket,
            Key=f"{location.key}/{name}",
            Body=current_timestamp().encode("utf-8"),
        )

    def _delete_sentinel(self, location: S3Location, name: str) -> None:
        LOGGER.debug("Deleting sentinel %s from %s", name, location.uri())
        self._s3.delete_object(Bucket=location.bucket, Key=f"{location.key}/{name}")

    def _update_local_sentinels(self, local_dir: Path, active: str) -> None:
        for sentinel in SENTINEL_NAMES:
            path = local_dir / sentinel
            if sentinel == active:
                path.write_text(current_timestamp() + "\n", encoding="utf-8")
            elif path.exists():
                path.unlink()

    def _handle_workset(self, parent_prefix: str, workset_prefix: str) -> None:
        workset_location = S3Location(self._root.bucket, workset_prefix.rstrip("/"))
        sentinels = self._list_sentinels(workset_location.bucket, workset_location.key)

        LOGGER.info("Evaluating workset %s with sentinels %s", workset_location.uri(), list(sentinels))

        if not sentinels:
            LOGGER.warning("Workset %s lacks sentinel files; skipping", workset_location.uri())
            return

        if SENTINEL_IGNORE in sentinels:
            LOGGER.info("Workset %s marked ignore", workset_location.uri())
            return

        if SENTINEL_COMPLETE in sentinels or SENTINEL_ERROR in sentinels or SENTINEL_IN_PROGRESS in sentinels:
            LOGGER.info("Workset %s already processed (sentinels=%s)", workset_location.uri(), list(sentinels))
            return

        if SENTINEL_READY not in sentinels:
            LOGGER.info("Workset %s not ready", workset_location.uri())
            return

        self._write_sentinel(workset_location, SENTINEL_LOCK)
        LOGGER.info("Lock sentinel created for %s; waiting for contention window", workset_location.uri())
        time.sleep(30)
        sentinels_after_lock = self._list_sentinels(workset_location.bucket, workset_location.key)
        if any(
            name in sentinels_after_lock and name not in {SENTINEL_READY, SENTINEL_LOCK}
            for name in SENTINEL_NAMES
        ):
            LOGGER.error("Contention detected for %s; aborting", workset_location.uri())
            self._write_sentinel(workset_location, SENTINEL_ERROR)
            return

        result: Optional[ProcessingResult] = None
        try:
            self._write_sentinel(workset_location, SENTINEL_IN_PROGRESS)
            result = self._process_single_workset(workset_location)
            if result.error:
                raise result.error
        except Exception as exc:  # noqa: BLE001 - log & propagate
            LOGGER.error("Processing failed for %s: %s", workset_location.uri(), exc)
            self._write_sentinel(workset_location, SENTINEL_ERROR)
            if result:
                self._export_results(result.local_dir, result.status)
            raise
        else:
            self._write_sentinel(workset_location, SENTINEL_COMPLETE)
            if result:
                self._export_results(result.local_dir, result.status)
        finally:
            self._delete_sentinel(workset_location, SENTINEL_LOCK)
            self._delete_sentinel(workset_location, SENTINEL_IN_PROGRESS)

    # -- core processing -----------------------------------------------------
    def _process_single_workset(self, workset_location: S3Location) -> ProcessingResult:
        local_dir = self._download_workset(workset_location)
        config = load_workset_configuration(local_dir)
        self._validate_stage_samples(local_dir / config.stage.samples_tsv, config)
        self._update_local_sentinels(local_dir, SENTINEL_IN_PROGRESS)

        stage_future = self._launch_stage_command(local_dir, config)
        cluster_future: Optional[S3WorksetMonitor._ClusterFuture] = None
        result: ProcessingResult
        try:
            cluster_future = self._ensure_cluster(config)
            stage_returncode = stage_future.wait()
            if stage_returncode != 0:
                raise MonitorError(f"Staging command failed with exit code {stage_returncode}")

            cluster_future.wait_for_ready()

            pipeline_dir = self._prepare_pipeline_directory(local_dir, config)
            self._copy_staged_manifest(local_dir, pipeline_dir, config)
            self._run_pipeline(pipeline_dir, config)
        except Exception as exc:  # noqa: BLE001 - capture failure
            self._update_local_sentinels(local_dir, SENTINEL_ERROR)
            result = ProcessingResult(local_dir=local_dir, status=SENTINEL_ERROR, error=exc)
        else:
            self._update_local_sentinels(local_dir, SENTINEL_COMPLETE)
            result = ProcessingResult(local_dir=local_dir, status=SENTINEL_COMPLETE, error=None)
        finally:
            try:
                stage_future.wait()
            except Exception:  # pragma: no cover - defensive
                LOGGER.warning("Failed to wait for staging command to exit", exc_info=True)

            if cluster_future and config.cluster.destroy_on_completion:
                try:
                    cluster_future.teardown()
                except Exception:  # pragma: no cover - defensive
                    LOGGER.warning("Cluster teardown encountered an error", exc_info=True)

        return result

    # -- staging -------------------------------------------------------------
    def _launch_stage_command(self, local_dir: Path, config: WorksetConfig):
        samples_path = local_dir / config.stage.samples_tsv
        cmd = [
            str(BIN_DIR / "daylily-stage-samples-from-local-to-headnode"),
            "--profile",
            config.aws_profile,
            "--region",
            config.aws_region,
        ]
        if config.stage.pem_key:
            cmd.extend(["--pem", str(Path.home() / ".ssh" / config.stage.pem_key)])
        cmd.extend(["--cluster", config.cluster.name])
        cmd.extend(config.stage.extra_args)
        cmd.append(str(samples_path))

        LOGGER.info("Launching staging command: %s", " ".join(cmd))

        process = subprocess.Popen(cmd, cwd=local_dir)

        class StageFuture:
            def wait(self) -> int:
                return process.wait()

        return StageFuture()

    # -- cluster -------------------------------------------------------------
    class _ClusterFuture:
        def __init__(self, create_proc: Optional[subprocess.Popen], config: ClusterConfig):
            self._proc = create_proc
            self._config = config

        def wait_for_ready(self) -> None:
            if self._proc is None:
                LOGGER.info("Cluster %s assumed ready", self._config.name)
                return
            LOGGER.info("Waiting for cluster creation to complete")
            rc = self._proc.wait()
            if rc != 0:
                raise MonitorError(f"Cluster creation failed with exit code {rc}")

        def teardown(self) -> None:
            if not self._config.destroy_on_completion:
                LOGGER.info("Skipping teardown for cluster %s", self._config.name)
                return
            cmd = [str(BIN_DIR / "daylily-delete-ephemeral-cluster"), "--cluster", self._config.name]
            LOGGER.info("Tearing down cluster with: %s", " ".join(cmd))
            subprocess.run(cmd, check=False)

    def _ensure_cluster(self, config: WorksetConfig) -> "S3WorksetMonitor._ClusterFuture":
        if config.cluster.allow_existing:
            LOGGER.info("Using existing cluster %s", config.cluster.name)
            return self._ClusterFuture(None, config.cluster)

        if not config.cluster.template:
            raise MonitorError("Cluster template must be provided when allow_existing is False")

        cmd = [
            str(BIN_DIR / "daylily-create-ephemeral-cluster"),
            "--cluster",
            config.cluster.name,
            "--template",
            config.cluster.template,
        ]
        cmd.extend(config.cluster.create_args)
        LOGGER.info("Launching cluster creation: %s", " ".join(cmd))
        proc = subprocess.Popen(cmd)
        return self._ClusterFuture(proc, config.cluster)

    # -- pipeline ------------------------------------------------------------
    def _prepare_pipeline_directory(self, local_dir: Path, config: WorksetConfig) -> Path:
        clone_cmd = ["day-clone", *config.pipeline.day_clone]
        LOGGER.info("Running day-clone: %s", " ".join(clone_cmd))
        subprocess.run(clone_cmd, cwd=local_dir, check=True)

        if config.pipeline.run_directory:
            pipeline_dir = local_dir / config.pipeline.run_directory
        else:
            candidate_dirs = [p for p in local_dir.iterdir() if p.is_dir()]
            if not candidate_dirs:
                raise MonitorError(
                    "No directories created by day-clone; provide pipeline.run_directory in daylily_work.yaml"
                )
            pipeline_dir = max(candidate_dirs, key=lambda p: p.stat().st_mtime)
        LOGGER.info("Using pipeline directory %s", pipeline_dir)
        return pipeline_dir

    def _copy_staged_manifest(self, local_dir: Path, pipeline_dir: Path, config: WorksetConfig) -> None:
        samples_src = local_dir / config.stage.samples_tsv
        samples_dest = pipeline_dir / config.pipeline.samples_config_path
        samples_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(samples_src, samples_dest)
        LOGGER.info("Copied samples manifest to %s", samples_dest)

        if config.stage.units_tsv:
            units_src = local_dir / config.stage.units_tsv
            units_dest = pipeline_dir / config.pipeline.units_config_path
            units_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(units_src, units_dest)
            LOGGER.info("Copied units manifest to %s", units_dest)

    def _run_pipeline(self, pipeline_dir: Path, config: WorksetConfig) -> None:
        command = ". dyoainit && dy-a {args} && dy-r {dy_r}".format(
            args=" ".join(config.pipeline.dy_a_args),
            dy_r=config.pipeline.dy_r_command,
        )
        LOGGER.info("Executing pipeline: %s", command)
        env = os.environ.copy()
        env.update(config.pipeline.environment)
        result = subprocess.run(["bash", "-lc", command], cwd=pipeline_dir, env=env)
        if result.returncode != 0:
            raise MonitorError(f"Pipeline command failed with exit code {result.returncode}")

    # -- validation ---------------------------------------------------------
    def _validate_stage_samples(self, samples_path: Path, config: WorksetConfig) -> None:
        if not samples_path.exists():
            raise MonitorError(f"Missing stage samples file: {samples_path}")

        LOGGER.info("Validating stage samples manifest %s", samples_path)
        with samples_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                for value in row.values():
                    if not value:
                        continue
                    if value.startswith("s3://"):
                        self._assert_s3_object_exists(value)
                    else:
                        candidate = samples_path.parent / value
                        if not candidate.exists():
                            raise MonitorError(f"Referenced file does not exist: {candidate}")

        LOGGER.info("Sample manifest validation complete")

    def _assert_s3_object_exists(self, uri: str) -> None:
        location = S3Location.parse(uri)
        try:
            self._s3.head_object(Bucket=location.bucket, Key=location.key)
        except botocore.exceptions.ClientError as exc:  # pragma: no cover - network dependent
            raise MonitorError(f"Missing S3 object {uri}") from exc

    # -- data transfer ------------------------------------------------------
    def _download_workset(self, workset_location: S3Location) -> Path:
        local_dir = self._local_root / workset_location.key.split("/")[-1]
        if local_dir.exists():
            shutil.rmtree(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=workset_location.bucket, Prefix=workset_location.key + "/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                name = key.split("/")[-1]
                if not name:
                    continue
                relative = key[len(workset_location.key) + 1 :]
                target_path = local_dir / relative
                target_path.parent.mkdir(parents=True, exist_ok=True)
                LOGGER.debug("Downloading %s to %s", key, target_path)
                with target_path.open("wb") as handle:
                    self._s3.download_fileobj(workset_location.bucket, key, handle)

        return local_dir

    def _export_results(self, local_dir: Path, status: str) -> None:
        if status == SENTINEL_COMPLETE:
            destination = self._root.join("complete", local_dir.name)
        elif status == SENTINEL_ERROR:
            destination = self._root.join("error", local_dir.name)
        else:
            destination = self._root.join("in_flight", local_dir.name)

        LOGGER.info("Uploading %s results to %s", status.replace("daylily.", ""), destination.uri())
        self._upload_directory(local_dir, destination)

    def _upload_directory(self, source: Path, destination: S3Location) -> None:
        for file_path in source.rglob("*"):
            if file_path.is_dir():
                continue
            relative = file_path.relative_to(source)
            key = f"{destination.key}/{relative.as_posix()}"
            LOGGER.debug("Uploading %s to %s/%s", file_path, destination.bucket, key)
            with file_path.open("rb") as handle:
                self._s3.upload_fileobj(handle, destination.bucket, key)

@dataclass
class ProcessingResult:
    """Outcome of processing a single workset."""

    local_dir: Path
    status: str
    error: Optional[Exception] = None

