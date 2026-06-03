from __future__ import annotations

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "dyec5128"
REGION = "us-west-2"
PROFILE = "lsmc"


REMOTE_SCRIPT = r"""
set -euo pipefail
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
for bucket in lsmc-dayoa-staging-usw2 lsmc-dayoa-analysis-results-usw2 lsmc-dayoa-runtime-assets-usw2; do
  uri="s3://${bucket}/runtime_cache_promotion_probe/dyec5128-${stamp}.txt"
  printf 'PROBE\t%s\t' "${uri}"
  if printf 'dyec5128 cache promotion probe %s\n' "${stamp}" | aws s3 cp - "${uri}" --only-show-errors; then
    printf 'WRITE_OK\n'
  else
    printf 'WRITE_FAIL\n'
  fi
done
"""


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            REMOTE_SCRIPT,
            profile=PROFILE,
            timeout=300,
            comment="probe writable s3 bucket for runtime cache promotion staging",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return getattr(result, "returncode", getattr(result, "rc", 0))


if __name__ == "__main__":
    raise SystemExit(main())
