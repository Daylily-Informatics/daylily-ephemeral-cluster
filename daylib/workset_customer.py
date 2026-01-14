"""Customer onboarding and management for multi-tenant workset system.

Handles customer provisioning, S3 bucket creation, and billing tags.
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger("daylily.workset_customer")


@dataclass
class CustomerConfig:
    """Customer configuration."""
    customer_id: str
    customer_name: str
    email: str
    s3_bucket: str
    max_concurrent_worksets: int = 5
    max_storage_gb: int = 1000
    billing_account_id: Optional[str] = None
    cost_center: Optional[str] = None


class CustomerManager:
    """Manage customer accounts and resources."""

    def __init__(
        self,
        region: str,
        profile: Optional[str] = None,
        bucket_prefix: str = "daylily-customer",
    ):
        """Initialize customer manager.

        Args:
            region: AWS region
            profile: AWS profile name
            bucket_prefix: Prefix for customer S3 buckets
        """
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.s3 = session.client("s3")
        self.dynamodb = session.resource("dynamodb")
        self.region = region
        self.bucket_prefix = bucket_prefix

        # Customer table for tracking
        self.customer_table_name = "daylily-customers"

    def create_customer_table_if_not_exists(self) -> None:
        """Create DynamoDB table for customer tracking."""
        try:
            table = self.dynamodb.Table(self.customer_table_name)
            table.load()
            LOGGER.info("Customer table %s already exists", self.customer_table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        LOGGER.info("Creating customer table %s", self.customer_table_name)
        table = self.dynamodb.create_table(
            TableName=self.customer_table_name,
            KeySchema=[
                {"AttributeName": "customer_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        LOGGER.info("Customer table created successfully")

    def onboard_customer(
        self,
        customer_name: str,
        email: str,
        max_concurrent_worksets: int = 5,
        max_storage_gb: int = 1000,
        billing_account_id: Optional[str] = None,
        cost_center: Optional[str] = None,
    ) -> CustomerConfig:
        """Onboard a new customer with provisioned resources.

        Args:
            customer_name: Customer name
            email: Customer email
            max_concurrent_worksets: Max concurrent worksets allowed
            max_storage_gb: Max storage in GB
            billing_account_id: Optional billing account ID
            cost_center: Optional cost center code

        Returns:
            CustomerConfig with provisioned resources
        """
        # Generate unique customer ID
        customer_id = self._generate_customer_id(customer_name)

        # Create S3 bucket
        bucket_name = f"{self.bucket_prefix}-{customer_id}"
        self._create_customer_bucket(bucket_name, customer_id, cost_center)

        # Create customer record
        config = CustomerConfig(
            customer_id=customer_id,
            customer_name=customer_name,
            email=email,
            s3_bucket=bucket_name,
            max_concurrent_worksets=max_concurrent_worksets,
            max_storage_gb=max_storage_gb,
            billing_account_id=billing_account_id,
            cost_center=cost_center,
        )

        self._save_customer_config(config)

        LOGGER.info(
            "Onboarded customer %s (ID: %s, bucket: %s)",
            customer_name,
            customer_id,
            bucket_name,
        )

        return config

    def _generate_customer_id(self, customer_name: str) -> str:
        """Generate unique customer ID.

        Args:
            customer_name: Customer name

        Returns:
            Customer ID
        """
        # Create ID from name + random suffix
        name_part = customer_name.lower().replace(" ", "-")[:20]
        random_part = secrets.token_hex(4)
        return f"{name_part}-{random_part}"

    def _create_customer_bucket(
        self,
        bucket_name: str,
        customer_id: str,
        cost_center: Optional[str],
    ) -> None:
        """Create S3 bucket for customer with appropriate tags.

        Args:
            bucket_name: Bucket name
            customer_id: Customer ID
            cost_center: Optional cost center
        """
        try:
            # Create bucket
            if self.region == "us-east-1":
                self.s3.create_bucket(Bucket=bucket_name)
            else:
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            # Enable versioning
            self.s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"},
            )

            # Add cost allocation tags
            tags = [
                {"Key": "Customer", "Value": customer_id},
                {"Key": "ManagedBy", "Value": "daylily-workset-monitor"},
                {"Key": "Environment", "Value": "production"},
            ]

            if cost_center:
                tags.append({"Key": "CostCenter", "Value": cost_center})

            self.s3.put_bucket_tagging(
                Bucket=bucket_name,
                Tagging={"TagSet": tags},
            )

            # Set lifecycle policy to manage costs
            lifecycle_policy = {
                "Rules": [
                    {
                        "Id": "DeleteOldWorksets",
                        "Status": "Enabled",
                        "Prefix": "worksets/",
                        "Expiration": {"Days": 90},
                    },
                    {
                        "Id": "TransitionToIA",
                        "Status": "Enabled",
                        "Prefix": "results/",
                        "Transitions": [
                            {"Days": 30, "StorageClass": "STANDARD_IA"},
                        ],
                    },
                ]
            }

            self.s3.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_policy,
            )

            LOGGER.info("Created customer bucket %s", bucket_name)

        except ClientError as e:
            if e.response["Error"]["Code"] == "BucketAlreadyExists":
                LOGGER.warning("Bucket %s already exists", bucket_name)
            else:
                LOGGER.error("Failed to create bucket %s: %s", bucket_name, e)
                raise

    def _save_customer_config(self, config: CustomerConfig) -> None:
        """Save customer configuration to DynamoDB.

        Args:
            config: Customer configuration
        """
        table = self.dynamodb.Table(self.customer_table_name)

        item = {
            "customer_id": config.customer_id,
            "customer_name": config.customer_name,
            "email": config.email,
            "s3_bucket": config.s3_bucket,
            "max_concurrent_worksets": config.max_concurrent_worksets,
            "max_storage_gb": config.max_storage_gb,
        }

        if config.billing_account_id:
            item["billing_account_id"] = config.billing_account_id
        if config.cost_center:
            item["cost_center"] = config.cost_center

        table.put_item(Item=item)
        LOGGER.info("Saved customer config for %s", config.customer_id)

    def get_customer_config(self, customer_id: str) -> Optional[CustomerConfig]:
        """Get customer configuration.

        Args:
            customer_id: Customer ID

        Returns:
            CustomerConfig or None if not found
        """
        table = self.dynamodb.Table(self.customer_table_name)

        try:
            response = table.get_item(Key={"customer_id": customer_id})
            item = response.get("Item")

            if not item:
                return None

            return CustomerConfig(
                customer_id=item["customer_id"],
                customer_name=item["customer_name"],
                email=item["email"],
                s3_bucket=item["s3_bucket"],
                max_concurrent_worksets=item.get("max_concurrent_worksets", 5),
                max_storage_gb=item.get("max_storage_gb", 1000),
                billing_account_id=item.get("billing_account_id"),
                cost_center=item.get("cost_center"),
            )

        except ClientError as e:
            LOGGER.error("Failed to get customer config: %s", e)
            return None

    def list_customers(self) -> List[CustomerConfig]:
        """List all customers.

        Returns:
            List of CustomerConfig objects
        """
        table = self.dynamodb.Table(self.customer_table_name)

        try:
            response = table.scan()
            items = response.get("Items", [])

            customers = []
            for item in items:
                customers.append(
                    CustomerConfig(
                        customer_id=item["customer_id"],
                        customer_name=item["customer_name"],
                        email=item["email"],
                        s3_bucket=item["s3_bucket"],
                        max_concurrent_worksets=item.get("max_concurrent_worksets", 5),
                        max_storage_gb=item.get("max_storage_gb", 1000),
                        billing_account_id=item.get("billing_account_id"),
                        cost_center=item.get("cost_center"),
                    )
                )

            return customers

        except ClientError as e:
            LOGGER.error("Failed to list customers: %s", e)
            return []

    def get_customer_usage(self, customer_id: str) -> Dict:
        """Get customer resource usage statistics.

        Args:
            customer_id: Customer ID

        Returns:
            Dict with usage statistics
        """
        config = self.get_customer_config(customer_id)
        if not config:
            return {}

        # Get S3 bucket size
        try:
            cloudwatch = boto3.client("cloudwatch", region_name=self.region)

            # Get bucket size metric (this is updated daily by AWS)
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": config.s3_bucket},
                    {"Name": "StorageType", "Value": "StandardStorage"},
                ],
                StartTime="2024-01-01",
                EndTime="2026-12-31",
                Period=86400,
                Statistics=["Average"],
            )

            datapoints = response.get("Datapoints", [])
            storage_bytes = datapoints[-1]["Average"] if datapoints else 0
            storage_gb = storage_bytes / (1024 ** 3)

        except Exception as e:
            LOGGER.warning("Failed to get storage metrics: %s", e)
            storage_gb = 0

        return {
            "customer_id": customer_id,
            "storage_gb": round(storage_gb, 2),
            "max_storage_gb": config.max_storage_gb,
            "storage_utilization_percent": round(
                (storage_gb / config.max_storage_gb) * 100, 2
            ) if config.max_storage_gb > 0 else 0,
        }


