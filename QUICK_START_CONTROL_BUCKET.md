# Quick Start: Control Bucket Configuration

## The Error
```
Control bucket is not configured for workset registration
```

## The Fix (Choose One)

### 1️⃣ Fastest: Set Environment Variable
```bash
export DAYLILY_CONTROL_BUCKET="lsmc-dayoa-omics-analysis-us-west-2"
./bin/daylily-workset-api --table-name daylily-worksets --region us-west-2 --verbose
```

### 2️⃣ Recommended: Use CLI Argument
```bash
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --control-bucket lsmc-dayoa-omics-analysis-us-west-2 \
    --verbose
```

### 3️⃣ Both: Environment Variable + CLI
```bash
export AWS_PROFILE=lsmc
export DAYLILY_CONTROL_BUCKET="lsmc-dayoa-omics-analysis-us-west-2"
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --profile lsmc \
    --verbose
```

## Verify It Works

### Check logs for success:
```
Integration layer initialized successfully
```

### Test workset creation:
```bash
curl -X POST http://localhost:8001/api/customers/test-customer/worksets \
  -H "Content-Type: application/json" \
  -d '{
    "workset_name": "test-workset",
    "pipeline_type": "snv",
    "reference_genome": "GRCh38"
  }'
```

## What Changed

✅ **CLI now supports `--control-bucket` argument**
✅ **Integration layer auto-initializes with control bucket**
✅ **Better error messages guide configuration**
✅ **Logs show initialization status**

## Key Points

- **Control bucket** = Monitor bucket = Where worksets are registered
- **DynamoDB** = Authoritative source for workset state
- **S3 artifacts** = Stored in control bucket prefix
- **Customer buckets** = NOT used for workset registration (control-plane refactor)

## Environment Variables

```bash
# Primary (recommended)
DAYLILY_CONTROL_BUCKET=your-bucket-name

# Fallback
DAYLILY_MONITOR_BUCKET=your-bucket-name

# AWS configuration
AWS_PROFILE=lsmc
AWS_DEFAULT_REGION=us-west-2
```

## Troubleshooting

**Q: Still getting the error?**
A: Check logs for "Integration layer initialized successfully"

**Q: What bucket should I use?**
A: Use your monitor/analysis bucket (e.g., `lsmc-dayoa-omics-analysis-us-west-2`)

**Q: Can I use a customer bucket?**
A: No - control-plane refactor requires a dedicated control bucket

**Q: How do I verify the bucket is accessible?**
A: `aws s3 ls s3://your-bucket-name/ --profile lsmc`

See `CONTROL_BUCKET_CONFIGURATION_GUIDE.md` for detailed documentation.

