"""HeartbeatManager — SNS topic + EventBridge Scheduler wiring (CP-015).

Ports ``bin/helpers/setup_cluster_heartbeat.py`` into an importable library.
Role resolution is delegated to :func:`daylily_ec.aws.iam.resolve_scheduler_role`.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resource naming
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeartbeatNames:
    """Derive deterministic resource names from a cluster name."""

    cluster_name: str

    @property
    def topic_name(self) -> str:
        return f"daylily-{self.cluster_name}-heartbeat"

    @property
    def schedule_name(self) -> str:
        # EventBridge Scheduler names are limited to 64 characters.
        return f"daylily-{self.cluster_name}-heartbeat"[:64]

    def topic_arn(self, account_id: str, region: str) -> str:
        return f"arn:aws:sns:{region}:{account_id}:{self.topic_name}"


def derive_names(cluster_name: str) -> HeartbeatNames:
    """Factory for :class:`HeartbeatNames`."""
    return HeartbeatNames(cluster_name=cluster_name)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class HeartbeatResult:
    """Outcome of :func:`ensure_heartbeat`."""

    success: bool
    topic_arn: str = ""
    schedule_name: str = ""
    role_arn: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# SNS topic + subscription
# ---------------------------------------------------------------------------


def ensure_topic_and_subscription(
    sns_client: Any,
    topic_name: str,
    email: str,
    region: str,
    account_id: str,
) -> str:
    """Create (or locate) the SNS topic and subscribe *email*.

    On ``AuthorizationError`` falls back to an existing topic ARN built
    from the naming convention — exactly matching the original helper.

    Returns the topic ARN.
    """
    try:
        topic_arn = sns_client.create_topic(Name=topic_name)["TopicArn"]
    except Exception as exc:
        err_code = _error_code(exc)
        if err_code != "AuthorizationError":
            raise
        # Fall back to existing topic when creation is forbidden.
        topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
        try:
            sns_client.get_topic_attributes(TopicArn=topic_arn)
        except Exception:
            raise RuntimeError(
                "SNS topic creation is forbidden and an existing topic "
                f"named '{topic_name}' was not found. Create the topic "
                "manually or grant SNS:CreateTopic permissions."
            ) from exc
        logger.warning(
            "SNS:CreateTopic not permitted; using existing topic %s",
            topic_arn,
        )

    # Subscribe email if not already subscribed.
    subs = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn).get(
        "Subscriptions", []
    )
    already = any(
        s.get("Protocol") == "email" and s.get("Endpoint") == email
        for s in subs
    )
    if not already:
        try:
            sns_client.subscribe(
                TopicArn=topic_arn, Protocol="email", Endpoint=email
            )
        except Exception as exc:
            err_code = _error_code(exc)
            if err_code == "AuthorizationError":
                raise RuntimeError(
                    "SNS subscription permissions are insufficient. "
                    "Confirm the topic has an email subscription for "
                    f"{email} or grant SNS:Subscribe."
                ) from exc
            raise

    return topic_arn


# ---------------------------------------------------------------------------
# EventBridge Scheduler schedule
# ---------------------------------------------------------------------------


def create_or_update_schedule(
    scheduler_client: Any,
    name: str,
    expression: str,
    role_arn: str,
    topic_arn: str,
    message: str,
    *,
    timezone: Optional[str] = None,
) -> None:
    """Create or update an EventBridge Scheduler schedule targeting SNS."""
    target: Dict[str, Any] = {
        "Arn": topic_arn,
        "RoleArn": role_arn,
        "Input": json.dumps({"default": message}),
    }
    kwargs: Dict[str, Any] = dict(
        Name=name,
        GroupName="default",
        ScheduleExpression=expression,
        FlexibleTimeWindow={"Mode": "OFF"},
        Target=target,
        State="ENABLED",
    )
    if timezone:
        kwargs["ScheduleExpressionTimezone"] = timezone

    try:
        scheduler_client.create_schedule(**kwargs)
    except Exception as exc:
        if _error_code(exc) != "ConflictException":
            raise
        scheduler_client.update_schedule(**kwargs)


# ---------------------------------------------------------------------------
# Top-level convenience
# ---------------------------------------------------------------------------


def ensure_heartbeat(
    sns_client: Any,
    scheduler_client: Any,
    *,
    cluster_name: str,
    region: str,
    account_id: str,
    email: str,
    schedule_expression: str,
    role_arn: str,
) -> HeartbeatResult:
    """Wire SNS topic + EventBridge Scheduler schedule.

    This is the main entry point for callers.  It is **non-fatal**: all
    exceptions are caught, logged, and returned in :attr:`HeartbeatResult.error`
    so the caller can decide whether to abort or continue.
    """
    names = derive_names(cluster_name)
    try:
        topic_arn = ensure_topic_and_subscription(
            sns_client,
            names.topic_name,
            email,
            region,
            account_id,
        )

        message = (
            f"Heartbeat for cluster '{cluster_name}' at "
            f"{int(time.time())} (epoch). Region: {region}."
        )

        create_or_update_schedule(
            scheduler_client,
            names.schedule_name,
            schedule_expression,
            role_arn,
            topic_arn,
            message,
        )

        logger.info(
            "Heartbeat configured: topic=%s schedule=%s",
            topic_arn,
            names.schedule_name,
        )
        return HeartbeatResult(
            success=True,
            topic_arn=topic_arn,
            schedule_name=names.schedule_name,
            role_arn=role_arn,
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning("Heartbeat setup failed (non-fatal): %s", exc)
        return HeartbeatResult(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _error_code(exc: BaseException) -> str:
    """Extract AWS error code from a botocore ClientError (or return '')."""
    resp = getattr(exc, "response", None)
    if resp and isinstance(resp, dict):
        return resp.get("Error", {}).get("Code", "")
    return ""

