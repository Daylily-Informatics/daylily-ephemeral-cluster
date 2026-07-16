"""Cluster tag editing helpers for DYEC-managed ParallelCluster stacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - botocore is present in supported envs
    ClientError = Exception  # type: ignore[misc,assignment]


MAX_TAG_KEY_LENGTH = 128
MAX_TAG_VALUE_LENGTH = 256
MAX_STACK_TAGS = 50
STABLE_STACK_STATUSES = frozenset(
    {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    }
)


class ClusterTagError(RuntimeError):
    """Raised when a requested cluster tag operation is invalid or fails."""


@dataclass(frozen=True)
class ClusterTagUpdate:
    """Result of a cluster stack tag read or update."""

    stack_id: str
    stack_status: str
    before_tags: dict[str, str]
    after_tags: dict[str, str]
    set_tags: dict[str, str]
    delete_keys: tuple[str, ...]
    updated: bool
    dry_run: bool
    waited: bool

    def to_payload(self, *, cluster: str, region: str) -> dict[str, Any]:
        return {
            "cluster": cluster,
            "region": region,
            "stack_id": self.stack_id,
            "stack_status": self.stack_status,
            "updated": self.updated,
            "dry_run": self.dry_run,
            "waited": self.waited,
            "set": self.set_tags,
            "deleted": list(self.delete_keys),
            "before": self.before_tags,
            "after": self.after_tags,
        }


def stack_id_from_describe_cluster(payload: Mapping[str, Any]) -> str:
    """Return the CloudFormation stack ARN from ``pcluster describe-cluster`` output."""

    stack_id = str(payload.get("cloudformationStackArn") or "").strip()
    if not stack_id:
        raise ClusterTagError(
            "pcluster describe-cluster did not return cloudformationStackArn; "
            "cannot edit cluster tags without an exact backing stack identity."
        )
    return stack_id


def parse_tag_assignments(values: Iterable[str] | None) -> dict[str, str]:
    """Parse repeated ``KEY=VALUE`` CLI arguments into a tag mapping."""

    parsed: dict[str, str] = {}
    for raw_value in values or ():
        if "=" not in raw_value:
            raise ClusterTagError(f"Tag assignment must be KEY=VALUE: {raw_value!r}")
        key, value = raw_value.split("=", 1)
        key = key.strip()
        if key in parsed:
            raise ClusterTagError(f"Duplicate tag assignment for key {key!r}")
        _validate_tag_key(key)
        _validate_tag_value(value)
        parsed[key] = value
    return parsed


def parse_tag_deletions(values: Iterable[str] | None) -> tuple[str, ...]:
    """Parse repeated tag delete keys."""

    parsed: list[str] = []
    seen: set[str] = set()
    for raw_value in values or ():
        key = raw_value.strip()
        if key in seen:
            raise ClusterTagError(f"Duplicate tag delete key {key!r}")
        _validate_tag_key(key)
        parsed.append(key)
        seen.add(key)
    return tuple(parsed)


def update_cluster_stack_tags(
    cfn_client: Any,
    *,
    stack_id: str,
    set_tags: Mapping[str, str] | None = None,
    delete_keys: Iterable[str] | None = None,
    wait: bool = True,
    dry_run: bool = False,
) -> ClusterTagUpdate:
    """Read or update tags on the CloudFormation stack backing a cluster."""

    requested_set = dict(set_tags or {})
    requested_delete = tuple(delete_keys or ())
    overlap = sorted(set(requested_set) & set(requested_delete))
    if overlap:
        raise ClusterTagError(
            "A tag key cannot be both set and deleted in one command: " + ", ".join(overlap)
        )

    stack = _describe_single_stack(cfn_client, stack_id)
    status = str(stack.get("StackStatus") or "")
    before_tags = _tags_list_to_dict(stack.get("Tags", []))
    if not requested_set and not requested_delete:
        return ClusterTagUpdate(
            stack_id=stack_id,
            stack_status=status,
            before_tags=before_tags,
            after_tags=before_tags,
            set_tags={},
            delete_keys=(),
            updated=False,
            dry_run=dry_run,
            waited=False,
        )

    if status not in STABLE_STACK_STATUSES:
        raise ClusterTagError(
            f"Stack {stack_id} is {status or 'UNKNOWN'}, not a stable updateable status."
        )

    missing_delete_keys = sorted(key for key in requested_delete if key not in before_tags)
    if missing_delete_keys:
        raise ClusterTagError(
            "Cannot delete missing cluster tag(s): " + ", ".join(missing_delete_keys)
        )

    after_tags = dict(before_tags)
    for key in requested_delete:
        after_tags.pop(key, None)
    after_tags.update(requested_set)
    if len(after_tags) > MAX_STACK_TAGS:
        raise ClusterTagError(
            f"CloudFormation stacks support at most {MAX_STACK_TAGS} tags; "
            f"requested result has {len(after_tags)} tags."
        )

    if after_tags == before_tags:
        return ClusterTagUpdate(
            stack_id=stack_id,
            stack_status=status,
            before_tags=before_tags,
            after_tags=after_tags,
            set_tags=requested_set,
            delete_keys=requested_delete,
            updated=False,
            dry_run=dry_run,
            waited=False,
        )

    if dry_run:
        return ClusterTagUpdate(
            stack_id=stack_id,
            stack_status=status,
            before_tags=before_tags,
            after_tags=after_tags,
            set_tags=requested_set,
            delete_keys=requested_delete,
            updated=False,
            dry_run=True,
            waited=False,
        )

    _update_stack_tags(cfn_client, stack, after_tags)
    waited = False
    if wait:
        cfn_client.get_waiter("stack_update_complete").wait(StackName=stack_id)
        waited = True
        stack = _describe_single_stack(cfn_client, stack_id)
        status = str(stack.get("StackStatus") or "")
        after_tags = _tags_list_to_dict(stack.get("Tags", []))

    return ClusterTagUpdate(
        stack_id=stack_id,
        stack_status=status,
        before_tags=before_tags,
        after_tags=after_tags,
        set_tags=requested_set,
        delete_keys=requested_delete,
        updated=True,
        dry_run=False,
        waited=waited,
    )


def _validate_tag_key(key: str) -> None:
    if not key:
        raise ClusterTagError("Tag key must not be empty.")
    if len(key) > MAX_TAG_KEY_LENGTH:
        raise ClusterTagError(f"Tag key exceeds {MAX_TAG_KEY_LENGTH} characters: {key!r}")
    if key.lower().startswith("aws:"):
        raise ClusterTagError(f"Tag key uses reserved AWS prefix: {key!r}")


def _validate_tag_value(value: str) -> None:
    if len(value) > MAX_TAG_VALUE_LENGTH:
        raise ClusterTagError(
            f"Tag value exceeds {MAX_TAG_VALUE_LENGTH} characters: {value!r}"
        )


def _describe_single_stack(cfn_client: Any, stack_id: str) -> dict[str, Any]:
    try:
        response = cfn_client.describe_stacks(StackName=stack_id)
    except ClientError as exc:
        raise ClusterTagError(f"Failed to describe cluster stack {stack_id}: {exc}") from exc
    stacks = response.get("Stacks", [])
    if len(stacks) != 1:
        raise ClusterTagError(
            f"Expected exactly one CloudFormation stack for {stack_id}, found {len(stacks)}."
        )
    stack = stacks[0]
    if not isinstance(stack, dict):
        raise ClusterTagError(f"Malformed CloudFormation stack response for {stack_id}.")
    return stack


def _tags_list_to_dict(tags: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for tag in tags:
        key = str(tag.get("Key") or tag.get("key") or "").strip()
        if not key:
            continue
        value = tag.get("Value") if "Value" in tag else tag.get("value")
        parsed[key] = "" if value is None else str(value)
    return dict(sorted(parsed.items()))


def _update_stack_tags(
    cfn_client: Any,
    stack: Mapping[str, Any],
    tags: Mapping[str, str],
) -> None:
    stack_id = str(stack.get("StackId") or stack.get("StackName") or "").strip()
    if not stack_id:
        raise ClusterTagError("CloudFormation stack response is missing StackId/StackName.")

    params = [
        {"ParameterKey": str(param["ParameterKey"]), "UsePreviousValue": True}
        for param in stack.get("Parameters", [])
        if param.get("ParameterKey")
    ]
    kwargs: dict[str, Any] = {
        "StackName": stack_id,
        "UsePreviousTemplate": True,
        "Parameters": params,
        "Tags": [{"Key": key, "Value": value} for key, value in sorted(tags.items())],
    }
    capabilities = stack.get("Capabilities") or ["CAPABILITY_NAMED_IAM"]
    if capabilities:
        kwargs["Capabilities"] = list(capabilities)
    role_arn = str(stack.get("RoleARN") or "").strip()
    if role_arn:
        kwargs["RoleARN"] = role_arn

    try:
        cfn_client.update_stack(**kwargs)
    except ClientError as exc:
        message = str(exc)
        if "No updates are to be performed" in message:
            return
        raise ClusterTagError(f"Failed to update cluster stack tags: {exc}") from exc
