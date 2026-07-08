#!/usr/bin/env python3
"""Run the live headnode budget deny probe for the DYEC 10.0.103 catalog cluster."""

from __future__ import annotations

import argparse
import json

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", default="cmdcat-103-all-20260707")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--remote-user", default="ubuntu")
    parser.add_argument("--cost-center", default="cmdcat-103-deny-20260707")
    args = parser.parse_args()

    target = resolve_headnode_instance_id(args.cluster, args.region, profile=args.profile)
    script = "\n".join(
        [
            "set -euo pipefail",
            "set +e",
            f"sbatch --comment {args.cost_center} --wrap 'echo SHOULD_NOT_RUN'",
            "rc=$?",
            "set -e",
            'echo "sbatch_rc=${rc}"',
            'test "${rc}" -ne 0',
        ]
    )
    try:
        result = run_shell(
            target.instance_id,
            args.region,
            script,
            profile=args.profile,
            as_user=args.remote_user,
            timeout=180,
            comment="Daylily budget deny probe",
        )
    except SsmCommandFailedError as exc:
        print(
            json.dumps(
                {
                    "cluster": args.cluster,
                    "instance_id": target.instance_id,
                    "cost_center": args.cost_center,
                    "ssm_command_id": exc.result.command_id,
                    "status": "unexpected_ssm_failure",
                    "response_code": exc.result.response_code,
                    "stdout": exc.result.stdout.strip(),
                    "stderr": exc.result.stderr.strip(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    combined = f"{result.stdout}\n{result.stderr}"
    expected = "cost-center monthly cap exceeded"
    status = "pass" if expected in combined and "Submitted batch job" not in combined else "fail"
    print(
        json.dumps(
            {
                "cluster": args.cluster,
                "instance_id": target.instance_id,
                "cost_center": args.cost_center,
                "ssm_command_id": result.command_id,
                "status": status,
                "expected_message": expected,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
