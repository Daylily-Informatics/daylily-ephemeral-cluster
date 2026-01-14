# Bug Fix: DynamoDB Table Creation Error

## Issue

When creating the DynamoDB table using `create_table_if_not_exists()`, the following error occurred:

```
botocore.exceptions.ClientError: An error occurred (ValidationException) when calling the CreateTable operation: 
One or more parameter values were invalid: ProvisionedThroughput should not be specified for index: 
state-priority-index when BillingMode is PAY_PER_REQUEST
```

## Root Cause

The table creation code was specifying `ProvisionedThroughput` for Global Secondary Indexes (GSIs) while using `BillingMode="PAY_PER_REQUEST"`. 

When using on-demand billing (`PAY_PER_REQUEST`), AWS DynamoDB automatically manages capacity and does not allow you to specify provisioned throughput values.

## Fix

**File**: `daylib/workset_state_db.py`

**Changed**: Removed `ProvisionedThroughput` specifications from GSI definitions when using `PAY_PER_REQUEST` billing mode.

### Before (Lines 105-131)
```python
GlobalSecondaryIndexes=[
    {
        "IndexName": "state-priority-index",
        "KeySchema": [...],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {  # ❌ This causes the error
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5,
        },
    },
    {
        "IndexName": "created-at-index",
        "KeySchema": [...],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {  # ❌ This causes the error
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5,
        },
    },
],
BillingMode="PAY_PER_REQUEST",
```

### After (Lines 105-123)
```python
GlobalSecondaryIndexes=[
    {
        "IndexName": "state-priority-index",
        "KeySchema": [...],
        "Projection": {"ProjectionType": "ALL"},
        # ✅ No ProvisionedThroughput specified
    },
    {
        "IndexName": "created-at-index",
        "KeySchema": [...],
        "Projection": {"ProjectionType": "ALL"},
        # ✅ No ProvisionedThroughput specified
    },
],
BillingMode="PAY_PER_REQUEST",
```

## Documentation Updates

Also updated `docs/WORKSET_MONITOR_ENHANCEMENTS.md` to reflect the correct AWS CLI command for creating the table with on-demand billing.

## Verification

### Test 1: Table Creation
```bash
python3 << 'EOF'
from daylib.workset_state_db import WorksetStateDB
db = WorksetStateDB("daylily-worksets-test", "us-west-2")
db.create_table_if_not_exists()
print("✓ Table created successfully")
EOF
```

**Result**: ✅ Success

### Test 2: Table Verification
```bash
aws dynamodb describe-table --table-name daylily-worksets-test --region us-west-2
```

**Result**: 
- ✅ Table Status: ACTIVE
- ✅ Billing Mode: PAY_PER_REQUEST
- ✅ GSI state-priority-index: ACTIVE
- ✅ GSI created-at-index: ACTIVE

### Test 3: Full Workflow
Tested complete workflow:
1. ✅ Register workset
2. ✅ Acquire lock
3. ✅ Update state
4. ✅ Release lock
5. ✅ Query queue depth

### Test 4: Unit Tests
```bash
pytest tests/ -v
```

**Result**: ✅ 19/19 tests passing

## Impact

- **Severity**: High (blocked table creation)
- **Scope**: All users attempting to create DynamoDB table
- **Fix Complexity**: Low (simple configuration change)
- **Breaking Changes**: None
- **Migration Required**: No

## Related AWS Documentation

From [AWS DynamoDB CreateTable API](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_CreateTable.html):

> When you create a table or index with BillingMode set to PAY_PER_REQUEST, you cannot specify ProvisionedThroughput. 
> If you do, you will receive a ValidationException.

## Recommendation

For production use, `PAY_PER_REQUEST` (on-demand) billing is recommended because:
- ✅ No capacity planning required
- ✅ Automatically scales with workload
- ✅ Pay only for what you use
- ✅ No throttling due to capacity limits
- ✅ Simpler to manage

If you need provisioned capacity for cost optimization with predictable workloads, you can modify the code to use `BillingMode="PROVISIONED"` and specify throughput values.

## Status

- ✅ Bug fixed
- ✅ Tests passing
- ✅ Documentation updated
- ✅ Verified with real AWS DynamoDB
- ✅ Ready for deployment

