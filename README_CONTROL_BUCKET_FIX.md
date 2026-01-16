# Control Bucket Configuration Fix - Complete Solution

## 🎯 Your Problem
```
Error: "Control bucket is not configured for workset registration"
```

## ✅ What Was Done

### 1. **Identified Root Cause**
- Workset creation endpoint requires control bucket (monitor bucket)
- No CLI argument to specify it
- Integration layer wasn't being initialized
- Error message didn't explain how to fix it

### 2. **Enhanced CLI** (`bin/daylily-workset-api`)
```bash
# NEW: You can now specify control bucket
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --control-bucket your-control-bucket-name
```

### 3. **Auto-Initialize Integration Layer**
The API server now automatically:
- Reads control bucket from CLI or environment variables
- Initializes `WorksetIntegration` with the control bucket
- Logs initialization status
- Passes integration to FastAPI app

### 4. **Improved Error Messages**
If control bucket is missing, you get helpful guidance:
```
Control bucket is not configured for workset registration. 
Please set DAYLILY_CONTROL_BUCKET or DAYLILY_MONITOR_BUCKET 
environment variable, or pass --control-bucket to the API server.
```

## 🚀 How to Fix (Choose One)

### Option 1: Environment Variable (Simplest)
```bash
export DAYLILY_CONTROL_BUCKET="lsmc-dayoa-omics-analysis-us-west-2"
./bin/daylily-workset-api --table-name daylily-worksets --region us-west-2
```

### Option 2: CLI Argument (Recommended)
```bash
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --control-bucket lsmc-dayoa-omics-analysis-us-west-2 \
    --verbose
```

### Option 3: Both (Most Explicit)
```bash
export AWS_PROFILE=lsmc
export DAYLILY_CONTROL_BUCKET="lsmc-dayoa-omics-analysis-us-west-2"
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --profile lsmc \
    --verbose
```

## ✔️ Verify It Works

### Check logs:
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

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **SOLUTION_SUMMARY.md** | Quick overview |
| **QUICK_START_CONTROL_BUCKET.md** | 3 configuration options |
| **CONTROL_BUCKET_CONFIGURATION_GUIDE.md** | Detailed guide |
| **CONTROL_PLANE_ARCHITECTURE_VERIFICATION.md** | Architecture compliance |
| **IMPLEMENTATION_CHECKLIST.md** | What was done |

## 🏗️ Architecture Compliance

✅ Worksets registered to **control bucket** (not customer buckets)
✅ **DynamoDB** is authoritative for state, locking, customer_id
✅ **S3** stores artifacts and sentinel files
✅ **Integration layer** bridges DynamoDB and S3
✅ **Control-plane refactor** requirements met

## 📋 Configuration Priority

1. **CLI Argument** (highest) - `--control-bucket`
2. **Environment Variable** - `DAYLILY_CONTROL_BUCKET`
3. **Environment Variable** - `DAYLILY_MONITOR_BUCKET`
4. **Integration Layer** (lowest) - `integration.bucket`

## 🔧 Files Changed

1. `bin/daylily-workset-api` - Added CLI args, integration init
2. `daylib/workset_api.py` - Better error messages
3. 7 new documentation files

## ❓ FAQ

**Q: What bucket should I use?**
A: Your monitor/analysis bucket (e.g., `lsmc-dayoa-omics-analysis-us-west-2`)

**Q: Can I use a customer bucket?**
A: No - control-plane refactor requires a dedicated control bucket

**Q: How do I verify the bucket is accessible?**
A: `aws s3 ls s3://your-bucket-name/ --profile lsmc`

**Q: Still getting the error?**
A: Check logs for "Integration layer initialized successfully"

## 🎉 Next Steps

1. Choose one configuration option above
2. Start the API server
3. Create a test workset via web interface
4. Verify DynamoDB record created
5. Verify S3 sentinel files in control bucket

**All done!** Your workset creation should now work. 🚀

