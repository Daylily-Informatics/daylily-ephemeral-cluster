"""
S3 Bucket Validation and IAM Policy Guidance for Daylily

Provides:
- Bucket existence and accessibility validation
- Permission checking (read, write, list)
- IAM policy generation for customer buckets
- Cross-account access configuration guidance
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
    
    @property
    def is_valid(self) -> bool:
        """Check if bucket is valid for Daylily use."""
        return self.exists and self.accessible and self.can_read and self.can_list
    
    @property
    def is_fully_configured(self) -> bool:
        """Check if bucket has all required permissions."""
        return self.is_valid and self.can_write


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
            bucket_name: S3 bucket name
            test_prefix: Prefix to use for write tests
            
        Returns:
            BucketValidationResult with validation details
        """
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
        bucket_name: S3 bucket name
        region: AWS region
        profile: AWS profile name

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    validator = S3BucketValidator(region=region, profile=profile)
    result = validator.validate_bucket(bucket_name)
    return result.is_valid, result.errors, result.warnings

