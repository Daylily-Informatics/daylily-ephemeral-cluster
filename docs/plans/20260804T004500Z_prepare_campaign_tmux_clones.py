#!/usr/bin/env python3
"""Prepare two exact-tag DayOA campaign clones in persistent tmux sessions."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
PARENT = "/fsx/analysis_results/preval-hiomr2"
LEDGER = "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T004100Z_take333_remaining_giab_hiomr2_ledger.md"

RUNS = {
    "take333lc": {
        "session": "dayoa_take333lc_hg002_5x5x_20260804",
        "source": f"{PARENT}/13-4-0/daylily-omics-analysis",
        "overlay": "hg002_bjuice_true5x5x_hiomr2_13_4_0.yaml",
        "dest_overlay": "hiomr2_take333lc_hg002_5x5x.yaml",
        "sed": "s/hg002-bjuice-5x5x-1340-20260802/take333lc/g; s/hg002_bjuice_true5x5x_13_4_0_20260802/hiomr2_take333lc_hg002_5x5x/g",
    },
    "remaining-giab": {
        "session": "dayoa_remaining_giab_20260804",
        "source": f"{PARENT}/take222/daylily-omics-analysis",
        "overlay": "hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml",
        "dest_overlay": "hiomr2_remaining_giab.yaml",
        "sed": "s/seqone_delivery_batch_id: take222/seqone_delivery_batch_id: remaining-giab/g; s/hiomr2_take222_hg003_hg004_na19235_na20775_fullcov/hiomr2_remaining_giab/g",
    },
}


def send(lines: list[str], session: str) -> str:
    commands = []
    for line in lines:
        escaped = line.replace("'", "'\\''")
        commands.append(f"tmux send-keys -t {session} '{escaped}' Enter")
    return "\n".join(commands)


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    chunks = ["set -euo pipefail"]
    manifests = "specimens.tsv samples.tsv libraries.tsv sequencing_inputs.tsv analysis_units.tsv analysis_unit_inputs.tsv"
    for analysis_id, cfg in RUNS.items():
        session = cfg["session"]
        root = f"{PARENT}/{analysis_id}"
        repo = f"{root}/daylily-omics-analysis"
        chunks.append(f"test ! -e {root}")
        chunks.append(f"! tmux has-session -t {session} 2>/dev/null")
        chunks.append(f"tmux new-session -d -s {session} 'bash -il'")
        lines = [
            "export DAYOA_AGENT_ID=codex-take333-remaining-giab-20260804",
            "export DAYOA_AGENT_KIND=codex",
            "export DAYOA_HUMAN_REQUESTOR='John Major'",
            f"export DAYOA_TMUX_SESSION={session}",
            f"export DAYOA_LEDGER_PATH={LEDGER}",
            "export DAY_PROJECT=RnD DAYLILY_COST_CENTER=RnD",
            f"mkdir -p {root}",
            f"dyec analysis visit --analysis-root {root} --mode write --intent 'Prepare exact-tag DayOA 13.4.3 campaign clone'",
            f"dyec analysis lock acquire --analysis-root {root} --operation write --intent 'Prepare and dry-run DayOA 13.4.3 campaign'",
            f"cd {PARENT}",
            f"day-clone -t 13.4.3 -d {analysis_id}",
            f"cd {repo}",
            "test \"$(git rev-parse HEAD)\" = \"$(git rev-parse 13.4.3^{})\"",
            f"for name in {manifests}; do cp {cfg['source']}/config/$name config/$name; done",
            f"cp {cfg['source']}/config/{cfg['overlay']} config/{cfg['dest_overlay']}",
            f"sed -i '{cfg['sed']}' config/{cfg['dest_overlay']}",
            f"printf 'SETUP_RC=0\\n' > /home/ubuntu/{analysis_id}_setup.rc",
            "source dyoainit",
            "dy-a slurm hg38",
        ]
        chunks.append(send(lines, session))
    chunks.append("tmux list-sessions")
    result = run_shell(target.instance_id, REGION, "\n".join(chunks), profile=PROFILE, as_user="ubuntu", timeout=300, comment="Prepare two DayOA campaign clones")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
