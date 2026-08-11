import gzip
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pysam

run = Path("/fsx/tmp/vep_johnmajor_sqjx8366_chr1_25_20260810T164600Z")
shards = run / "shards"
base = "JohnMajor-SQJX8366-30x-WGS-Sequencing_com-01-17-26.snp-indel.genome.chr1-25.vep114.GRCh38"
plain = run / f"{base}.vcf"
final = run / f"{base}.vcf.gz"
manifest = run / f"{base}.manifest.txt"

input_count = output_count = 0
with plain.open("wt") as merged:
    for chrom in range(1, 26):
        shard = shards / f"chr{chrom}.vep114.GRCh38.vcf.gz"
        if not shard.is_file() or shard.stat().st_size == 0:
            raise RuntimeError(f"missing shard: {shard}")
        with gzip.open(shard, "rt") as src:
            for line in src:
                if line.startswith("#"):
                    if chrom == 1:
                        merged.write(line)
                    continue
                if line.split("\t", 1)[0] != str(chrom):
                    raise RuntimeError(f"out-of-order record in chr{chrom}: {line[:100]}")
                merged.write(line)
                output_count += 1

with gzip.open("/fsx/tmp/vep_johnmajor_sqjx8366_20260810T132200Z/input.vcf.gz", "rt") as src:
    for line in src:
        if not line.startswith("#") and line.split("\t", 1)[0] in {str(i) for i in range(1, 26)}:
            input_count += 1

csq_headers = sum(1 for line in plain.open() if line.startswith("##INFO=<ID=CSQ,"))
if input_count != output_count:
    raise RuntimeError(f"record count mismatch: input={input_count} output={output_count}")
if csq_headers != 1:
    raise RuntimeError(f"CSQ header count: {csq_headers}")

pysam.tabix_compress(str(plain), str(final), force=True)
pysam.tabix_index(str(final), preset="vcf", force=True)
plain.unlink()

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

index = Path(str(final) + ".tbi")
with manifest.open("wt") as out:
    out.write(f"created_utc={datetime.now(timezone.utc).isoformat()}\n")
    out.write("scope=chr1-chr25\n")
    out.write(f"input_records={input_count}\noutput_records={output_count}\ncsq_header_count={csq_headers}\n")
    for artifact in (final, index):
        out.write(f"artifact={artifact.name}\tbytes={artifact.stat().st_size}\tsha256={digest(artifact)}\n")
