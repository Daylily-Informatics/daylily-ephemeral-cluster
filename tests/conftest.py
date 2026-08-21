from __future__ import annotations

import datetime as dt
import uuid

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    optional_group = parser.getgroup("daylily optional tests")
    optional_group.addoption(
        "--run-catalog-snapshot-tests",
        action="store_true",
        default=False,
        help="Run the slow repository-catalog snapshot test modules.",
    )

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
        "--live-staging-reference-s3-uri",
        default="",
        help="Reference S3 URI for live staging example tests.",
    )
    group.addoption(
        "--live-staging-control-data-s3-uri",
        default="",
        help="Control/validation data S3 URI for live staging example tests.",
    )
    group.addoption(
        "--live-staging-stage-s3-uri",
        default="",
        help="Staging S3 URI for live staging example tests.",
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


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--run-catalog-snapshot-tests"):
        return
    skip_catalog_snapshot = pytest.mark.skip(
        reason=(
            "optional repository-catalog snapshot test; "
            "pass --run-catalog-snapshot-tests to enable"
        )
    )
    for item in items:
        if "catalog_snapshot" in item.keywords:
            item.add_marker(skip_catalog_snapshot)


@pytest.fixture(scope="session")
def live_staging_run_id() -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:6]}"
