"""
S3 Bucket Validation and IAM Policy Guidance for Daylily

Provides:
- Bucket existence and accessibility validation
- Permission checking (read, write, list)
- IAM policy generation for customer buckets
- Cross-account access configuration guidance
- Linked bucket management for file registry
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    """Return current UTC time in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.s3_bucket_validator")


@dataclass
class BucketValidationResult:
    """Result of S3 bucket validation."""
    bucket_name: str
    exists: bool = False
    accessible: bool = False
    can_read: bool = False
    can_write: bool = False
    can_list: bool = False
    region: Optional[str] = None
    owner_account: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    remediation_steps: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if bucket is valid for Daylily use."""
        return self.exists and self.accessible and self.can_read and self.can_list

    @property
    def is_fully_configured(self) -> bool:
        """Check if bucket has all required permissions."""
        return self.is_valid and self.can_write

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "bucket_name": self.bucket_name,
            "exists": self.exists,
            "accessible": self.accessible,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "can_list": self.can_list,
            "region": self.region,
            "owner_account": self.owner_account,
            "is_valid": self.is_valid,
            "is_fully_configured": self.is_fully_configured,
            "errors": self.errors,
            "warnings": self.warnings,
            "remediation_steps": self.remediation_steps,
        }


@dataclass
class LinkedBucket:
    """A customer-linked S3 bucket configuration."""
    bucket_id: str  # Unique identifier for this linked bucket
    customer_id: str
    bucket_name: str
    bucket_type: str = "primary"  # primary, secondary, archive, shared
    display_name: Optional[str] = None  # User-friendly name
    description: Optional[str] = None

    # Validation status
    is_validated: bool = False
    validation_timestamp: Optional[str] = None
    can_read: bool = False
    can_write: bool = False
    can_list: bool = False
    region: Optional[str] = None

    # Access configuration
    prefix_restriction: Optional[str] = None  # Restrict access to specific prefix
    read_only: bool = False  # If true, prevent writes

    # Timestamps
    linked_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


class S3BucketValidator:
    """Validate S3 bucket configuration and permissions for Daylily."""
    
    def __init__(
        self,
        region: str = "us-west-2",
        profile: Optional[str] = None,
    ):
        """Initialize validator.
        
        Args:
            region: AWS region
            profile: AWS profile name
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        
        session = boto3.Session(**session_kwargs)
        self.s3 = session.client("s3")
        self.sts = session.client("sts")
        self.region = region
        
        # Get current account ID
        try:
            self.account_id = self.sts.get_caller_identity()["Account"]
        except Exception:
            self.account_id = None
    
    def validate_bucket(
        self,
        bucket_name: str,
        test_prefix: str = "daylily-validation-test/",
    ) -> BucketValidationResult:
        """Validate an S3 bucket for Daylily use.

        Args:
            bucket_name: S3 bucket name (can include s3:// prefix)
            test_prefix: Prefix to use for write tests

        Returns:
            BucketValidationResult with validation details
        """
        # Strip s3:// prefix if provided
        if bucket_name.startswith("s3://"):
            bucket_name = bucket_name[5:]

        result = BucketValidationResult(bucket_name=bucket_name)
        
        # Check bucket exists
        try:
            self.s3.head_bucket(Bucket=bucket_name)
            result.exists = True
            result.accessible = True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                result.errors.append(f"Bucket '{bucket_name}' does not exist")
            elif error_code == "403":
                result.exists = True  # Bucket exists but no access
                result.errors.append(
                    f"Access denied to bucket '{bucket_name}'. "
                    "Check IAM permissions or bucket policy."
                )
            else:
                result.errors.append(f"Error accessing bucket: {e}")
            return result
        
        # Get bucket region
        try:
            location = self.s3.get_bucket_location(Bucket=bucket_name)
            result.region = location.get("LocationConstraint") or "us-east-1"
        except ClientError:
            result.warnings.append("Could not determine bucket region")
        
        # Test list permission
        result.can_list = self._test_list_permission(bucket_name, result)
        
        # Test read permission
        result.can_read = self._test_read_permission(bucket_name, result)
        
        # Test write permission
        result.can_write = self._test_write_permission(bucket_name, test_prefix, result)
        
        return result
    
    def _test_list_permission(
        self,
        bucket_name: str,
        result: BucketValidationResult,
    ) -> bool:
        """Test if we can list objects in the bucket."""
        try:
            self.s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            return True
        except ClientError as e:
            result.errors.append(f"Cannot list bucket contents: {e}")
            return False
    
    def _test_read_permission(
        self,
        bucket_name: str,
        result: BucketValidationResult,
    ) -> bool:
        """Test if we can read objects from the bucket."""
        try:
            # Try to list and read first object
            response = self.s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            if response.get("Contents"):
                key = response["Contents"][0]["Key"]
                self.s3.head_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as e:
            if "NoSuchKey" not in str(e):
                result.warnings.append(f"Read permission uncertain: {e}")
            return True  # Assume OK if bucket is empty

    def _test_write_permission(
        self,
        bucket_name: str,
        test_prefix: str,
        result: BucketValidationResult,
    ) -> bool:
        """Test if we can write objects to the bucket."""
        test_key = f"{test_prefix.rstrip('/')}/daylily-permission-test.txt"
        try:
            # Write test object
            self.s3.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=b"Daylily permission test",
            )
            # Clean up
            self.s3.delete_object(Bucket=bucket_name, Key=test_key)
            return True
        except ClientError as e:
            result.warnings.append(
                f"Cannot write to bucket (read-only access): {e}. "
                "Write permission is required for workset submission."
            )
            return False

    def generate_customer_bucket_policy(
        self,
        bucket_name: str,
        daylily_account_id: str,
        daylily_role_arn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate S3 bucket policy for cross-account Daylily access.

        Args:
            bucket_name: Customer's S3 bucket name
            daylily_account_id: Daylily service account ID
            daylily_role_arn: Optional specific role ARN

        Returns:
            S3 bucket policy document
        """
        principal = (
            {"AWS": daylily_role_arn}
            if daylily_role_arn
            else {"AWS": f"arn:aws:iam::{daylily_account_id}:root"}
        )

        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DaylilyReadAccess",
                    "Effect": "Allow",
                    "Principal": principal,
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:GetObjectTagging",
                    ],
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                },
                {
                    "Sid": "DaylilyListAccess",
                    "Effect": "Allow",
                    "Principal": principal,
                    "Action": [
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                    ],
                    "Resource": f"arn:aws:s3:::{bucket_name}",
                },
                {
                    "Sid": "DaylilyWriteAccess",
                    "Effect": "Allow",
                    "Principal": principal,
                    "Action": [
                        "s3:PutObject",
                        "s3:PutObjectTagging",
                        "s3:DeleteObject",
                    ],
                    "Resource": f"arn:aws:s3:::{bucket_name}/worksets/*",
                    "Condition": {
                        "StringEquals": {
                            "s3:x-amz-acl": "bucket-owner-full-control"
                        }
                    },
                },
            ],
        }

    def generate_iam_policy_for_bucket(
        self,
        bucket_name: str,
        read_only: bool = False,
    ) -> Dict[str, Any]:
        """Generate IAM policy for accessing a customer bucket.

        Args:
            bucket_name: S3 bucket name
            read_only: If True, generate read-only policy

        Returns:
            IAM policy document
        """
        statements = [
            {
                "Sid": "ListBucket",
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}",
            },
            {
                "Sid": "ReadObjects",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:GetObjectTagging",
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            },
        ]

        if not read_only:
            statements.append({
                "Sid": "WriteObjects",
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:PutObjectTagging",
                    "s3:DeleteObject",
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}/worksets/*",
            })

        return {
            "Version": "2012-10-17",
            "Statement": statements,
        }

    def get_setup_instructions(
        self,
        bucket_name: str,
        validation_result: BucketValidationResult,
        daylily_account_id: str = "108782052779",
    ) -> str:
        """Generate setup instructions based on validation result.

        Args:
            bucket_name: S3 bucket name
            validation_result: Result from validate_bucket()
            daylily_account_id: Daylily service account ID

        Returns:
            Markdown-formatted setup instructions
        """
        instructions = []

        if not validation_result.exists:
            instructions.append(f"""
## Create S3 Bucket

Your bucket `{bucket_name}` does not exist. Create it with:

```bash
aws s3 mb s3://{bucket_name} --region {self.region}
```
""")

        if validation_result.exists and not validation_result.accessible:
            bucket_policy = self.generate_customer_bucket_policy(
                bucket_name, daylily_account_id
            )
            instructions.append(f"""
## Configure Bucket Policy

Add this bucket policy to allow Daylily access:

```json
{json.dumps(bucket_policy, indent=2)}
```

Apply with:
```bash
aws s3api put-bucket-policy --bucket {bucket_name} --policy file://bucket-policy.json
```
""")

        if validation_result.accessible and not validation_result.can_write:
            instructions.append(f"""
## Enable Write Access

Your bucket is accessible but Daylily cannot write results.
Add write permissions to the bucket policy for the `worksets/` prefix.
""")

        if validation_result.is_fully_configured:
            instructions.append(f"""
## ✅ Bucket Ready

Your bucket `{bucket_name}` is fully configured for Daylily:
- ✅ Bucket exists and is accessible
- ✅ Can list bucket contents
- ✅ Can read objects
- ✅ Can write to worksets/ prefix
""")

        return "\n".join(instructions) if instructions else "No setup required."


def validate_bucket_for_workset(
    bucket_name: str,
    region: str = "us-west-2",
    profile: Optional[str] = None,
) -> Tuple[bool, List[str], List[str]]:
    """Convenience function to validate a bucket for workset submission.

    Args:
        bucket_name: S3 bucket name (can include s3:// prefix)
        region: AWS region
        profile: AWS profile name

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    # Strip s3:// prefix if provided
    if bucket_name.startswith("s3://"):
        bucket_name = bucket_name[5:]

    validator = S3BucketValidator(region=region, profile=profile)
    result = validator.validate_bucket(bucket_name)
    return result.is_valid, result.errors, result.warnings


class LinkedBucketManager:
    """Manage linked S3 buckets per customer with validation and persistence."""

    def __init__(
        self,
        table_name: str = "daylily-linked-buckets",
        region: str = "us-west-2",
        profile: Optional[str] = None,
        auto_create_table: bool = True,
    ):
        """Initialize linked bucket manager.

        Args:
            table_name: DynamoDB table for linked bucket configs
            region: AWS region
            profile: AWS profile name
            auto_create_table: Automatically create table if it doesn't exist
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        LOGGER.info(
            "Initializing LinkedBucketManager: table=%s, region=%s, profile=%s",
            table_name, region, profile
        )

        session = boto3.Session(**session_kwargs)
        self.dynamodb = session.resource("dynamodb")
        self.table_name = table_name
        self.table = self.dynamodb.Table(table_name)
        self.validator = S3BucketValidator(region=region, profile=profile)
        self.region = region
        self.profile = profile

        # Sanity logging/guards so mis-bound DynamoDB resources surface immediately
        LOGGER.info(
            "LinkedBucketManager bound to table: %s (region=%s)",
            self.table.table_name,
            self.region,
        )
        assert hasattr(self.table, "table_name")

        # Auto-create table if requested
        if auto_create_table:
            self.create_table_if_not_exists()

    def create_table_if_not_exists(self) -> None:
        """Create DynamoDB table for linked buckets."""
        try:
            self.table.load()
            LOGGER.info("Linked buckets table %s already exists", self.table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating linked buckets table %s", self.table_name)
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {"AttributeName": "bucket_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "bucket_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer-id-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Linked buckets table created successfully")

    def _generate_bucket_id(self, customer_id: str, bucket_name: str) -> str:
        """Generate unique bucket ID."""
        hash_input = f"{customer_id}:{bucket_name}"
        return f"lb-{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

    def link_bucket(
        self,
        customer_id: str,
        bucket_name: str,
        bucket_type: str = "secondary",
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        prefix_restriction: Optional[str] = None,
        read_only: bool = False,
        validate: bool = True,
    ) -> Tuple[LinkedBucket, BucketValidationResult]:
        """Link an S3 bucket to a customer account.

        Args:
            customer_id: Customer ID
            bucket_name: S3 bucket name (can include s3:// prefix)
            bucket_type: Type of bucket (primary, secondary, archive, shared)
            display_name: User-friendly display name
            description: Description of bucket purpose
            prefix_restriction: Restrict access to specific prefix
            read_only: If true, prevent writes
            validate: Whether to validate the bucket

        Returns:
            Tuple of (LinkedBucket, BucketValidationResult)
        """
        # Strip s3:// prefix if provided
        if bucket_name.startswith("s3://"):
            bucket_name = bucket_name[5:]

        bucket_id = self._generate_bucket_id(customer_id, bucket_name)

        # Validate bucket if requested
        validation_result = BucketValidationResult(bucket_name=bucket_name)
        if validate:
            validation_result = self.validator.validate_bucket(
                bucket_name,
                test_prefix=f"daylily-uploads/{customer_id}/"
            )
            # Add remediation steps based on errors
            self._add_remediation_steps(validation_result)

        linked_bucket = LinkedBucket(
            bucket_id=bucket_id,
            customer_id=customer_id,
            bucket_name=bucket_name,
            bucket_type=bucket_type,
            display_name=display_name or bucket_name,
            description=description,
            is_validated=validation_result.is_valid,
            validation_timestamp=_utc_now_iso() if validate else None,
            can_read=validation_result.can_read,
            can_write=validation_result.can_write if not read_only else False,
            can_list=validation_result.can_list,
            region=validation_result.region,
            prefix_restriction=prefix_restriction,
            read_only=read_only,
        )

        # Save to DynamoDB
        self._save_linked_bucket(linked_bucket)

        LOGGER.info(
            "Linked bucket %s for customer %s (valid: %s, can_write: %s)",
            bucket_name, customer_id, linked_bucket.is_validated, linked_bucket.can_write
        )

        return linked_bucket, validation_result

    def _add_remediation_steps(self, result: BucketValidationResult) -> None:
        """Add specific remediation steps based on validation errors."""
        if not result.exists:
            result.remediation_steps.append(
                f"Create the S3 bucket: aws s3 mb s3://{result.bucket_name}"
            )
            return

        if not result.accessible:
            result.remediation_steps.extend([
                "The bucket exists but is not accessible. This typically means:",
                "1. The bucket is in a different AWS account - configure a bucket policy for cross-account access",
                "2. IAM permissions are missing - attach the required S3 read/list permissions to your role",
                f"Required IAM actions: s3:ListBucket, s3:GetObject on bucket {result.bucket_name}",
            ])
            return

        if not result.can_list:
            result.remediation_steps.append(
                f"Add s3:ListBucket permission for arn:aws:s3:::{result.bucket_name}"
            )

        if not result.can_read:
            result.remediation_steps.append(
                f"Add s3:GetObject permission for arn:aws:s3:::{result.bucket_name}/*"
            )

        if not result.can_write:
            result.remediation_steps.extend([
                "Write permission is required for uploading files and storing results.",
                f"Add s3:PutObject permission for arn:aws:s3:::{result.bucket_name}/*",
                "For cross-account buckets, ensure the bucket policy allows writes from the Daylily account.",
            ])

    def _save_linked_bucket(self, linked_bucket: LinkedBucket) -> None:
        """Save linked bucket configuration to DynamoDB."""
        item = {
            "bucket_id": linked_bucket.bucket_id,
            "customer_id": linked_bucket.customer_id,
            "bucket_name": linked_bucket.bucket_name,
            "bucket_type": linked_bucket.bucket_type,
            "display_name": linked_bucket.display_name or linked_bucket.bucket_name,
            "description": linked_bucket.description or "",
            "is_validated": linked_bucket.is_validated,
            "validation_timestamp": linked_bucket.validation_timestamp or "",
            "can_read": linked_bucket.can_read,
            "can_write": linked_bucket.can_write,
            "can_list": linked_bucket.can_list,
            "region": linked_bucket.region or "",
            "prefix_restriction": linked_bucket.prefix_restriction or "",
            "read_only": linked_bucket.read_only,
            "linked_at": linked_bucket.linked_at,
            "updated_at": _utc_now_iso(),
        }

        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "Saving linked bucket to DynamoDB table %s: bucket_id=%s, customer_id=%s, bucket_name=%s",
                self.table_name, linked_bucket.bucket_id, linked_bucket.customer_id, linked_bucket.bucket_name
            )

        try:
            self.table.put_item(Item=item)
            LOGGER.info("Successfully saved linked bucket %s to table %s", linked_bucket.bucket_id, self.table_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            LOGGER.error(
                "DynamoDB error saving linked bucket: table=%s, error_code=%s, message=%s",
                self.table_name, error_code, error_msg
            )
            if error_code == "ResourceNotFoundException":
                LOGGER.error(
                    "Table %s does not exist. Create it with LinkedBucketManager.create_table_if_not_exists()",
                    self.table_name
                )
            raise

    def get_linked_bucket(self, bucket_id: str) -> Optional[LinkedBucket]:
        """Get a linked bucket by ID."""
        try:
            response = self.table.get_item(Key={"bucket_id": bucket_id})
            if "Item" not in response:
                return None
            return self._item_to_linked_bucket(response["Item"])
        except ClientError as e:
            LOGGER.error("Failed to get linked bucket %s: %s", bucket_id, str(e))
            return None

    # Alias for get_linked_bucket
    def get_bucket(self, bucket_id: str) -> Optional[LinkedBucket]:
        """Alias for get_linked_bucket."""
        return self.get_linked_bucket(bucket_id)

    def list_customer_buckets(self, customer_id: str) -> List[LinkedBucket]:
        """List all linked buckets for a customer."""
        try:
            response = self.table.query(
                IndexName="customer-id-index",
                KeyConditionExpression="customer_id = :cid",
                ExpressionAttributeValues={":cid": customer_id},
            )
            return [self._item_to_linked_bucket(item) for item in response.get("Items", [])]
        except ClientError as e:
            LOGGER.error("Failed to list buckets for customer %s: %s", customer_id, str(e))
            return []

    def _item_to_linked_bucket(self, item: Dict[str, Any]) -> LinkedBucket:
        """Convert DynamoDB item to LinkedBucket."""
        return LinkedBucket(
            bucket_id=item["bucket_id"],
            customer_id=item["customer_id"],
            bucket_name=item["bucket_name"],
            bucket_type=item.get("bucket_type", "secondary"),
            display_name=item.get("display_name"),
            description=item.get("description"),
            is_validated=item.get("is_validated", False),
            validation_timestamp=item.get("validation_timestamp"),
            can_read=item.get("can_read", False),
            can_write=item.get("can_write", False),
            can_list=item.get("can_list", False),
            region=item.get("region"),
            prefix_restriction=item.get("prefix_restriction"),
            read_only=item.get("read_only", False),
            linked_at=item.get("linked_at", ""),
            updated_at=item.get("updated_at", ""),
        )

    def revalidate_bucket(self, bucket_id: str) -> Tuple[Optional[LinkedBucket], BucketValidationResult]:
        """Re-validate a linked bucket and update its status."""
        linked_bucket = self.get_linked_bucket(bucket_id)
        if not linked_bucket:
            return None, BucketValidationResult(bucket_name="unknown", errors=["Bucket not found"])

        # Re-validate
        validation_result = self.validator.validate_bucket(
            linked_bucket.bucket_name,
            test_prefix=f"daylily-uploads/{linked_bucket.customer_id}/"
        )
        self._add_remediation_steps(validation_result)

        # Update status
        linked_bucket.is_validated = validation_result.is_valid
        linked_bucket.validation_timestamp = _utc_now_iso()
        linked_bucket.can_read = validation_result.can_read
        linked_bucket.can_write = validation_result.can_write if not linked_bucket.read_only else False
        linked_bucket.can_list = validation_result.can_list
        linked_bucket.region = validation_result.region

        self._save_linked_bucket(linked_bucket)

        return linked_bucket, validation_result

    def unlink_bucket(self, bucket_id: str) -> bool:
        """Remove a linked bucket."""
        try:
            self.table.delete_item(Key={"bucket_id": bucket_id})
            LOGGER.info("Unlinked bucket %s", bucket_id)
            return True
        except ClientError as e:
            LOGGER.error("Failed to unlink bucket %s: %s", bucket_id, str(e))
            return False

    def update_bucket(
        self,
        bucket_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        bucket_type: Optional[str] = None,
        prefix_restriction: Optional[str] = None,
        read_only: Optional[bool] = None,
    ) -> Optional[LinkedBucket]:
        """Update a linked bucket's editable properties.

        Args:
            bucket_id: The bucket ID to update
            display_name: New display name (optional)
            description: New description (optional)
            bucket_type: New bucket type (optional)
            prefix_restriction: New prefix restriction (optional)
            read_only: New read-only setting (optional)

        Returns:
            Updated LinkedBucket or None if not found
        """
        # First get the existing bucket
        existing = self.get_bucket(bucket_id)
        if existing is None:
            LOGGER.warning("Cannot update bucket %s: not found", bucket_id)
            return None

        # Build update expression
        update_parts: List[str] = []
        expression_values: Dict[str, Any] = {}
        expression_names: Dict[str, str] = {}

        if display_name is not None:
            update_parts.append("#dn = :dn")
            expression_names["#dn"] = "display_name"
            expression_values[":dn"] = display_name

        if description is not None:
            update_parts.append("description = :desc")
            expression_values[":desc"] = description

        if bucket_type is not None:
            update_parts.append("bucket_type = :bt")
            expression_values[":bt"] = bucket_type

        if prefix_restriction is not None:
            update_parts.append("prefix_restriction = :pr")
            expression_values[":pr"] = prefix_restriction

        if read_only is not None:
            update_parts.append("read_only = :ro")
            expression_values[":ro"] = read_only
            # If switching to read-only, also update can_write
            if read_only:
                update_parts.append("can_write = :cw")
                expression_values[":cw"] = False

        # Always update updated_at
        update_parts.append("updated_at = :ua")
        expression_values[":ua"] = _utc_now_iso()

        if not update_parts:
            LOGGER.debug("No updates to apply for bucket %s", bucket_id)
            return existing

        try:
            update_kwargs = {
                "Key": {"bucket_id": bucket_id},
                "UpdateExpression": "SET " + ", ".join(update_parts),
                "ExpressionAttributeValues": expression_values,
                "ReturnValues": "ALL_NEW",
            }
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            response = self.table.update_item(**update_kwargs)
            item = response.get("Attributes", {})

            updated_bucket = LinkedBucket(
                bucket_id=item.get("bucket_id", ""),
                customer_id=item.get("customer_id", ""),
                bucket_name=item.get("bucket_name", ""),
                bucket_type=item.get("bucket_type", "secondary"),
                display_name=item.get("display_name"),
                description=item.get("description"),
                is_validated=item.get("is_validated", False),
                validation_timestamp=item.get("validation_timestamp"),
                can_read=item.get("can_read", False),
                can_write=item.get("can_write", False),
                can_list=item.get("can_list", False),
                region=item.get("region"),
                prefix_restriction=item.get("prefix_restriction"),
                read_only=item.get("read_only", False),
                linked_at=item.get("linked_at", ""),
            )

            LOGGER.info("Updated bucket %s", bucket_id)
            return updated_bucket

        except ClientError as e:
            LOGGER.error("Failed to update bucket %s: %s", bucket_id, str(e))
            return None

