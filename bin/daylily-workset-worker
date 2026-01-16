#!/usr/bin/env python3
"""Poll DynamoDB for ready worksets and execute them via the WorksetMonitor."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from daylib.workset_monitor import (
    MonitorConfig,
    WorksetMonitor,
    Workset,
    configure_logging,
    SENTINEL_FILES,
)
from daylib.workset_state_db import WorksetState, WorksetStateDB

LOGGER = logging.getLogger("daylily.workset_worker")

# Processing steps in order
PROCESSING_STEPS = [
    "initializing",
    "stage_samples",
    "clone_pipeline",
    "push_stage_files",
    "run_pipeline",
    "export_results",
    "finalizing",
]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll DynamoDB and run Daylily worksets using the monitor pipeline",
    )
    parser.add_argument("config", type=Path, help="Path to the YAML configuration file")
    parser.add_argument(
        "--table-name",
        default=os.environ.get("DAYLILY_DYNAMODB_TABLE", "daylily-worksets"),
        help="DynamoDB table name for workset state",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (defaults to config value)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (defaults to config value)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll iteration and exit",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Maximum number of ready worksets to process per poll",
    )
    parser.add_argument(
        "--no-write-sentinels",
        dest="write_sentinels",
        action="store_false",
        help="Disable writing S3 sentinel files for compatibility",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.set_defaults(write_sentinels=True)
    return parser.parse_args(argv)


def build_worker_id() -> str:
    return f"worker-{socket.gethostname()}-{os.getpid()}"


class ProgressTracker:
    """Track and report workset processing progress to DynamoDB."""

    def __init__(
        self,
        state_db: WorksetStateDB,
        workset_id: str,
        cluster_name: Optional[str] = None,
    ):
        self.state_db = state_db
        self.workset_id = workset_id
        self.cluster_name = cluster_name
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._current_step: Optional[str] = None

    def update_step(self, step: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        """Update current processing step in DynamoDB."""
        self._current_step = step
        LOGGER.info("Workset %s: step=%s", self.workset_id, step)
        try:
            self.state_db.update_progress(
                workset_id=self.workset_id,
                current_step=step,
                cluster_name=self.cluster_name,
                started_at=self.started_at,
                metrics=metrics,
            )
        except Exception as e:
            LOGGER.warning(
                "Failed to update progress for %s (step=%s): %s",
                self.workset_id,
                step,
                str(e),
            )

    def set_cluster(self, cluster_name: str) -> None:
        """Update cluster name."""
        self.cluster_name = cluster_name
        self.update_step(self._current_step or "initializing")

    def finish(self, metrics: Optional[Dict[str, Any]] = None) -> None:
        """Mark processing as finished."""
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            self.state_db.update_progress(
                workset_id=self.workset_id,
                current_step="complete",
                finished_at=finished_at,
                metrics=metrics,
            )
        except Exception as e:
            LOGGER.warning(
                "Failed to update finish progress for %s: %s",
                self.workset_id,
                str(e),
            )


def process_workset(
    monitor: WorksetMonitor,
    state_db: WorksetStateDB,
    workset_record: dict,
    *,
    owner_id: str,
    write_sentinels: bool,
) -> None:
    workset_id = workset_record.get("workset_id")
    if not workset_id:
        LOGGER.warning("Skipping workset with missing workset_id: %s", workset_record)
        return

    if not state_db.acquire_lock(workset_id, owner_id):
        LOGGER.debug("Lock contention for %s", workset_id)
        return

    prefix = workset_record.get("prefix") or f"{monitor.config.monitor.normalised_prefix()}{workset_id}/"
    workset = monitor.build_workset(workset_id, prefix=prefix)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Initialize progress tracker
    progress = ProgressTracker(state_db, workset_id)
    progress.update_step("initializing")

    try:
        if write_sentinels:
            monitor.write_sentinel(workset, SENTINEL_FILES["lock"], timestamp)

        state_db.update_state(
            workset_id=workset_id,
            new_state=WorksetState.IN_PROGRESS,
            reason=f"Workset claimed by {owner_id}",
        )
        if write_sentinels:
            monitor.write_sentinel(workset, SENTINEL_FILES["in_progress"], timestamp)

        # Process workset - the monitor will handle the pipeline steps
        # We update progress to "processing" before handing off
        progress.update_step("processing")
        monitor.process_workset(workset)

        # Mark as finalizing while we gather metrics
        progress.update_step("finalizing")
        metrics = monitor.load_workset_metrics(workset)

        # Update final state with metrics
        state_db.update_state(
            workset_id=workset_id,
            new_state=WorksetState.COMPLETE,
            reason=f"Workset completed by {owner_id}",
            metrics=metrics,
        )
        progress.finish(metrics)

        if write_sentinels:
            monitor.write_sentinel(
                workset,
                SENTINEL_FILES["complete"],
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
        LOGGER.info("Workset %s completed successfully", workset_id)

    except Exception as exc:
        LOGGER.exception("Workset %s failed", workset_id)
        metrics = monitor.load_workset_metrics(workset)
        state_db.update_state(
            workset_id=workset_id,
            new_state=WorksetState.ERROR,
            reason=f"Workset failed in worker {owner_id}",
            error_details=str(exc),
            metrics=metrics,
        )
        if write_sentinels:
            error_message = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\t{exc}"
            monitor.write_sentinel(workset, SENTINEL_FILES["error"], error_message)
    finally:
        state_db.release_lock(workset_id, owner_id)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    config = MonitorConfig.load(args.config)
    if args.region:
        config.aws.region = args.region
    if args.profile:
        config.aws.profile = args.profile

    state_db = WorksetStateDB(
        table_name=args.table_name,
        region=config.aws.region,
        profile=config.aws.profile if config.aws.profile else None,
    )

    monitor = WorksetMonitor(
        config,
        dry_run=False,
        debug=False,
        state_db=state_db,
    )

    owner_id = build_worker_id()
    LOGGER.info("Starting workset worker as %s", owner_id)

    while True:
        ready = state_db.get_ready_worksets_prioritized(limit=args.batch_size)
        if not ready:
            LOGGER.debug("No ready worksets found")
        for record in ready:
            process_workset(
                monitor,
                state_db,
                record,
                owner_id=owner_id,
                write_sentinels=args.write_sentinels,
            )

        if args.once:
            break

        LOGGER.debug("Sleeping %.1fs before next poll", config.monitor.poll_interval_seconds)
        time.sleep(config.monitor.poll_interval_seconds)

    return 0


if __name__ == "__main__":
    sys.exit(main())
