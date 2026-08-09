#!/usr/bin/env python3
"""Collect a compact read-only Take222 report evidence bundle from the headnode."""

from __future__ import annotations

import base64
import hashlib
import io
import re
import tarfile
import uuid
from pathlib import Path

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
OUTPUT = Path("/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts/source-data")


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    archive_path = f"/tmp/codex_take222_report_evidence_{uuid.uuid4().hex}.tar.gz"
    script = r"""set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-report-20260804
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T070646Z_take222_hiomr2_runtime_results_report_ledger.md'
dyec analysis visit --analysis-root __ROOT__ --mode read --intent 'Collect compact Take222 report evidence'
cd __ROOT__/daylily-omics-analysis
evidence_dir=$(mktemp -d /tmp/take222-report-evidence.XXXXXX)
trap 'rm -rf "$evidence_dir"' EXIT
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python - "$evidence_dir" <<'PY'
import collections
import csv
import json
import shutil
import sys
from pathlib import Path

out = Path(sys.argv[1])
results = Path('results/day/hg38')
mqc_path = results / 'reports/DAY_final_multiqc_data/multiqc_data.json'
mqc = json.loads(mqc_path.read_text(encoding='utf-8'))

raw_keys = [
    'multiqc_alignstats',
    'multiqc_alignstats_input_provenance',
    'multiqc_snakemake_specimens',
    'multiqc_snakemake_samples',
    'multiqc_snakemake_libraries',
    'multiqc_snakemake_sequencing_inputs',
    'multiqc_snakemake_analysis_units',
    'multiqc_snakemake_analysis_unit_inputs',
    'multiqc_snakemake_benchmark_aggregate_rules',
    'multiqc_snakemake_benchmark_rows',
    'multiqc_library_summary',
    'multiqc_alignment_qc_outputs',
    'multiqc_bcftools_variant_stats',
    'multiqc_contamination',
    'multiqc_coverage_evenness_two_combo',
    'multiqc_giab_concordance',
    'multiqc_htd_calls',
    'multiqc_inferred_sex_chromosome_complement',
    'multiqc_norm_cov_evenness_combo',
    'multiqc_peddy_sample_qc',
    'multiqc_relatedness_lr',
    'multiqc_relatedness_sr',
    'multiqc_rtg_vcfstats',
    'multiqc_sentdhiomr2_nicu',
    'multiqc_sentdhiomr2_nicu_artifacts',
    'multiqc_sentdhiomr2_roh_upd',
    'multiqc_sentdhiomr2_segdup',
    'multiqc_sentdhiomr2_sniffles2',
    'multiqc_sentdhiomr2_tiddit',
    'multiqc_seqfu',
    'multiqc_sequence_qc_outputs',
    'multiqc_sex_gender_rollup',
    'multiqc_site_mix_contam',
    'multiqc_site_mix_donor',
    'multiqc_smn12_orthogonal_calls',
    'multiqc_general_stats',
]
raw = mqc.get('report_saved_raw_data', {})
extract = {
    'report_creation_date': mqc.get('report_creation_date'),
    'config_report_comment': mqc.get('config_report_comment'),
    'config_report_header_info': mqc.get('config_report_header_info'),
    'config_version': mqc.get('config_version'),
    'report_data_sources': mqc.get('report_data_sources'),
    'report_general_stats_data': mqc.get('report_general_stats_data'),
    'report_general_stats_headers': mqc.get('report_general_stats_headers'),
    'saved_raw_data': {key: raw.get(key) for key in raw_keys},
}
(out / 'take222_multiqc_extract.json').write_text(
    json.dumps(extract, indent=2, sort_keys=True), encoding='utf-8'
)

def classify(path: Path) -> tuple[str, str]:
    rel = path.as_posix().lower()
    name = path.name.lower()
    if '/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/' in rel:
        return 'inflection_package', 'delivery'
    if '/reports/' in rel:
        return 'reporting', 'multiqc_or_report'
    if '/nicu-research/' in rel or '.nicu-' in name:
        for caller in ('dysgu', 'manta', 'severus', 'sniffles2', 'longreadsv', 'jasmine', 'survivor', 'octopusv', 'truvari'):
            if caller in rel:
                return 'nicu_mega', caller
        return 'nicu_mega', 'other'
    if '/concordance' in rel or 'rtg' in name or 'truvari' in name:
        return 'benchmarking', 'concordance'
    if '/segdup/' in rel or 'smn12' in rel:
        return 'targeted_calling', 'smn_segdup'
    if 'sniffles' in rel:
        return 'structural_variants', 'sniffles2'
    if 'tiddit' in rel:
        return 'structural_variants', 'tiddit'
    if 'longreadsv' in rel:
        return 'structural_variants', 'longreadsv'
    if 'cnvscope' in rel or '/cnv/' in rel:
        return 'copy_number', 'cnv'
    if 'roh' in rel or 'upd' in rel:
        return 'roh_upd', 'roh_upd'
    if '/snv/' in rel or name.endswith(('.vcf.gz', '.g.vcf.gz')):
        return 'small_variants', 'vcf_gvcf'
    if 'alignqc' in rel or 'fastqc' in rel or 'mosdepth' in rel or 'alignstats' in rel:
        return 'alignment_qc', 'qc'
    if '/benchmarks/' in rel or name.endswith('.bench.tsv'):
        return 'runtime_benchmark', 'benchmark'
    if '/logs/' in rel or name.endswith('.log'):
        return 'logs', 'log'
    if '/provenance/' in rel or 'receipt' in name or 'manifest' in name:
        return 'provenance', 'manifest_receipt'
    return 'other', 'other'

files = [p for p in results.rglob('*') if p.is_file()]
category_counts = collections.Counter()
category_bytes = collections.Counter()
subtype_counts = collections.Counter()
with (out / 'take222_output_inventory.tsv').open('w', encoding='utf-8', newline='') as handle:
    writer = csv.writer(handle, delimiter='\t')
    writer.writerow(['path', 'bytes', 'mtime_epoch', 'category', 'subtype'])
    for path in sorted(files):
        stat = path.stat()
        category, subtype = classify(path)
        category_counts[category] += 1
        category_bytes[category] += stat.st_size
        subtype_counts[f'{category}:{subtype}'] += 1
        writer.writerow([path.as_posix(), stat.st_size, int(stat.st_mtime), category, subtype])

summary = {
    'analysis_root': '__ROOT__',
    'results_root': str(results),
    'file_count': len(files),
    'total_bytes': sum(p.stat().st_size for p in files),
    'category_counts': dict(sorted(category_counts.items())),
    'category_bytes': dict(sorted(category_bytes.items())),
    'subtype_counts': dict(sorted(subtype_counts.items())),
    'final_multiqc_html': {
        'path': str(results / 'reports/DAY_final_multiqc.html'),
        'bytes': (results / 'reports/DAY_final_multiqc.html').stat().st_size,
        'mtime_epoch': int((results / 'reports/DAY_final_multiqc.html').stat().st_mtime),
    },
    'multiqc_data_json': {
        'path': str(mqc_path),
        'bytes': mqc_path.stat().st_size,
        'mtime_epoch': int(mqc_path.stat().st_mtime),
    },
}
(out / 'take222_output_inventory_summary.json').write_text(
    json.dumps(summary, indent=2, sort_keys=True), encoding='utf-8'
)

manifest_payload = {}
for path in sorted(results.glob('deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/take222/*/package_manifest.json')):
    manifest_payload[path.as_posix()] = json.loads(path.read_text(encoding='utf-8'))
(out / 'take222_inflection_package_manifests.json').write_text(
    json.dumps(manifest_payload, indent=2, sort_keys=True), encoding='utf-8'
)

configs = out / 'config'
configs.mkdir()
for name in (
    'analysis_units.tsv', 'analysis_unit_inputs.tsv', 'sequencing_inputs.tsv',
    'samples.tsv', 'specimens.tsv', 'libraries.tsv',
    'hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml',
    'take222_manifest_validation_receipt.json',
    'take222_bjuice_preval_config_receipt.json',
):
    source = Path('config') / name
    if source.exists():
        shutil.copy2(source, configs / name)

selected = out / 'selected_artifacts'
selected.mkdir()
selected_patterns = (
    '*giabHC*concordance.mqc.tsv', '*smn12.summary.tsv', '*smn12.summary.json',
    '*truvari-metrics.json', '*truvari-summary.tsv', '*terminal_receipt.json',
    '*evidence_manifest.json', '*treatment*.tsv',
)
copied = set()
for pattern in selected_patterns:
    for path in results.rglob(pattern):
        if not path.is_file() or path in copied:
            continue
        copied.add(path)
        destination = selected / path.relative_to(results)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
(out / 'selected_artifact_count.txt').write_text(f'{len(copied)}\n', encoding='utf-8')
PY
tar -C "$evidence_dir" -czf __ARCHIVE__ .
printf 'ARCHIVE_BYTES=%s\n' "$(stat -c %s __ARCHIVE__)"
printf 'ARCHIVE_SHA256=%s\n' "$(sha256sum __ARCHIVE__ | cut -d ' ' -f 1)"
""".replace("__ROOT__", ROOT).replace("__ARCHIVE__", archive_path)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=600,
            comment="Collect Take222 report evidence",
        )
    except SsmCommandFailedError as exc:
        print(exc.result.stdout)
        if exc.result.stderr:
            print(exc.result.stderr)
        return 1
    if result.status != "Success":
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return 1

    size_match = re.search(r"ARCHIVE_BYTES=(\d+)", result.stdout)
    sha_match = re.search(r"ARCHIVE_SHA256=([0-9a-f]{64})", result.stdout)
    if not size_match or not sha_match:
        raise RuntimeError("Take222 archive size or SHA-256 was not returned")
    archive_size = int(size_match.group(1))
    archive_sha256 = sha_match.group(1)

    chunk_size = 14_000
    chunks = []
    for chunk_index in range((archive_size + chunk_size - 1) // chunk_size):
        chunk_script = rf"""set -euo pipefail
printf '%s\n' 'BEGIN_CHUNK'
dd if={archive_path} bs={chunk_size} skip={chunk_index} count=1 status=none | base64 -w 0
printf '\n%s\n' 'END_CHUNK'
"""
        try:
            chunk_result = run_shell(
                target.instance_id,
                REGION,
                chunk_script,
                profile=PROFILE,
                as_user="ubuntu",
                timeout=120,
                comment=f"Read Take222 evidence chunk {chunk_index + 1}",
            )
        except SsmCommandFailedError as exc:
            print(exc.result.stdout)
            if exc.result.stderr:
                print(exc.result.stderr)
            return 1
        chunk_match = re.search(
            r"BEGIN_CHUNK\n([A-Za-z0-9+/=\n]+)\nEND_CHUNK",
            chunk_result.stdout,
        )
        if not chunk_match:
            raise RuntimeError(f"Evidence chunk {chunk_index + 1} markers were not found")
        chunks.append(base64.b64decode("".join(chunk_match.group(1).split()), validate=True))

    cleanup_script = f"set -euo pipefail\nrm -f {archive_path}\n"
    run_shell(
        target.instance_id,
        REGION,
        cleanup_script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=120,
        comment="Remove Take222 temporary evidence archive",
    )
    payload = b"".join(chunks)
    if len(payload) != archive_size:
        raise RuntimeError(f"Evidence archive size mismatch: {len(payload)} != {archive_size}")
    if hashlib.sha256(payload).hexdigest() != archive_sha256:
        raise RuntimeError("Evidence archive SHA-256 mismatch")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"Unsafe archive member: {member.name}")
        archive.extractall(OUTPUT, filter="data")

    files = [path for path in OUTPUT.rglob("*") if path.is_file()]
    print(f"collected_files={len(files)}")
    print(f"collected_bytes={sum(path.stat().st_size for path in files)}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
