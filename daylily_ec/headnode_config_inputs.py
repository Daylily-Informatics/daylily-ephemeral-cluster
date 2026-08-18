"""Strict state-backed inputs for headnode configuration.

Headnode configure needs the two repository deploy-key secret references that
were selected when the cluster was created.  The create state record already
points at the immutable next-run configuration containing those explicit
triplets, so operators should not have to copy secret ARNs into every refresh
command.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from daylily_ec.config.triplets import load_config
from daylily_ec.scripts.common import CommandError
from daylily_ec.state.store import config_dir, load_state_record


_SECRET_ARN_PATTERN = re.compile(
    r"arn:(aws(?:-us-gov)?):secretsmanager:([a-z0-9-]+):(\d{12}):secret:"
    r"[A-Za-z0-9/_+=.@-]+"
)


@dataclass(frozen=True)
class HeadnodeDeployKeyInputs:
    """Validated deploy-key references and their non-secret provenance."""

    dyec_secret_arn: str
    dayoa_secret_arn: str
    source: str
    state_path: Path | None = None
    config_path: Path | None = None


def _load_state_record(path: Path):
    candidate = path.expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        raise CommandError(f"Headnode state file must be a regular file: {candidate}")
    try:
        return load_state_record(candidate), candidate.resolve()
    except Exception as exc:  # noqa: BLE001 - convert persisted-state failures to CLI errors
        raise CommandError(f"Unable to read headnode state file {candidate}: {exc}") from exc


def _latest_state_for_cluster(cluster_name: str):
    matches: list[tuple[str, Path, object]] = []
    for candidate in sorted(config_dir().glob("state_*.json")):
        try:
            record, resolved_path = _load_state_record(candidate)
        except CommandError:
            continue
        if record.cluster_name == cluster_name:
            matches.append((record.run_id, resolved_path, record))
    if not matches:
        raise CommandError(
            "No usable local create-state record was found for cluster "
            f"'{cluster_name}'. Supply --state-file or both exact deploy-key options."
        )
    _run_id, state_path, record = sorted(matches, key=lambda item: (item[0], str(item[1])))[-1]
    return record, state_path


def _validate_secret_arn(value: str, *, field: str, region: str) -> str:
    candidate = value.strip()
    match = _SECRET_ARN_PATTERN.fullmatch(candidate)
    if not match:
        raise CommandError(f"{field} must be an exact Secrets Manager ARN.")
    if match.group(2) != region:
        raise CommandError(f"{field} must be in the selected region '{region}'.")
    return candidate


def _configured_value(config, key: str, *, config_path: Path) -> str:
    triplet = config.ephemeral_cluster.config.get(key)
    value = triplet.set_value.strip() if triplet is not None else ""
    if not value:
        raise CommandError(
            f"Headnode config {config_path} lacks an explicit {key} set value. "
            "Re-create the state/config or provide both exact deploy-key options."
        )
    return value


def resolve_headnode_deploy_key_inputs(
    *,
    cluster_name: str,
    region: str,
    state_file: Path | None,
    dyec_deploy_key_secret_arn: str,
    dayoa_deploy_key_secret_arn: str,
) -> HeadnodeDeployKeyInputs:
    """Resolve either both direct key references or the exact create-state config.

    Direct inputs are deliberately all-or-nothing.  With neither supplied,
    this uses the newest local create-state record for the selected cluster,
    or an explicit ``--state-file`` when provided.  It never combines values
    from those two authority sources.
    """

    dyec_value = dyec_deploy_key_secret_arn.strip()
    dayoa_value = dayoa_deploy_key_secret_arn.strip()
    if bool(dyec_value) != bool(dayoa_value):
        raise CommandError(
            "Provide both --dyec-deploy-key-secret-arn and "
            "--dayoa-deploy-key-secret-arn, or provide neither to use the cluster state."
        )
    if dyec_value:
        if state_file is not None:
            raise CommandError(
                "Use either --state-file or both direct deploy-key options; do not mix sources."
            )
        return HeadnodeDeployKeyInputs(
            dyec_secret_arn=_validate_secret_arn(
                dyec_value,
                field="--dyec-deploy-key-secret-arn",
                region=region,
            ),
            dayoa_secret_arn=_validate_secret_arn(
                dayoa_value,
                field="--dayoa-deploy-key-secret-arn",
                region=region,
            ),
            source="explicit-options",
        )

    record, resolved_state_path = (
        _load_state_record(state_file)
        if state_file is not None
        else _latest_state_for_cluster(cluster_name)
    )
    if record.cluster_name != cluster_name:
        raise CommandError(
            f"Headnode state {resolved_state_path} belongs to cluster "
            f"'{record.cluster_name}', not '{cluster_name}'."
        )
    if record.region != region:
        raise CommandError(
            f"Headnode state {resolved_state_path} has region '{record.region}', not '{region}'."
        )
    if not record.resolved_cli_config_path:
        raise CommandError(
            f"Headnode state {resolved_state_path} does not record a resolved cluster config path."
        )

    config_path = Path(record.resolved_cli_config_path).expanduser()
    if config_path.is_symlink() or not config_path.is_file():
        raise CommandError(
            f"Headnode state references a missing or non-regular config: {config_path}"
        )
    config_path = config_path.resolve()
    try:
        config = load_config(config_path)
    except Exception as exc:  # noqa: BLE001 - normalize config parsing errors for CLI callers
        raise CommandError(f"Unable to read headnode config {config_path}: {exc}") from exc

    configured_cluster = _configured_value(config, "cluster_name", config_path=config_path)
    if configured_cluster != cluster_name:
        raise CommandError(
            f"Headnode config {config_path} names cluster '{configured_cluster}', not '{cluster_name}'."
        )
    return HeadnodeDeployKeyInputs(
        dyec_secret_arn=_validate_secret_arn(
            _configured_value(config, "dyec_deploy_key_secret_arn", config_path=config_path),
            field="dyec_deploy_key_secret_arn",
            region=region,
        ),
        dayoa_secret_arn=_validate_secret_arn(
            _configured_value(config, "dayoa_deploy_key_secret_arn", config_path=config_path),
            field="dayoa_deploy_key_secret_arn",
            region=region,
        ),
        source="state-file",
        state_path=resolved_state_path,
        config_path=config_path,
    )
