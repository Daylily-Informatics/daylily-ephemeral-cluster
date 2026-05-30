set -euo pipefail
prefix=s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/probe/
probe_uri=s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/probe/_dyec_probe_1780093062.txt
tmp=$(mktemp)
printf 'dyec catalog validation probe %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$tmp"
aws s3 ls "$prefix" >/tmp/dyec_probe_ls.out 2>/tmp/dyec_probe_ls.err || true
cat /tmp/dyec_probe_ls.err >&2
aws s3 cp "$tmp" "$probe_uri"
aws s3 rm "$probe_uri"
rm -f "$tmp"