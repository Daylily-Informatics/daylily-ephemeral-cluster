from __future__ import annotations

import datetime as dt
import uuid

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("daylily live aws")
    group.addoption(
        "--run-live-staging-examples",
        action="store_true",
        default=False,
        help="Run live staging example tests against an existing cluster.",
    )
    group.addoption(
        "--live-staging-profile",
        default="daylily-service-lsmc",
        help="AWS profile for live staging example tests.",
    )
    group.addoption(
        "--live-staging-region",
        default="us-west-2",
        help="AWS region for live staging example tests.",
    )
    group.addoption(
        "--live-staging-cluster",
        default="mk-gotime3",
        help="Existing ParallelCluster name for live staging example tests.",
    )
    group.addoption(
        "--live-staging-reference-bucket",
        default="s3://lsmc-dayoa-omics-analysis-us-west-2",
        help="Reference bucket URI for live staging example tests.",
    )
    group.addoption(
        "--live-staging-non-dryrun",
        action="store_true",
        default=False,
        help="Launch real workflows instead of dry-runs during live staging example tests.",
    )
    group.addoption(
        "--live-staging-workflow-timeout-minutes",
        type=int,
        default=30,
        help="Maximum minutes to wait for each live staging workflow to finish.",
    )


@pytest.fixture(scope="session")
def live_staging_run_id() -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:6]}"
