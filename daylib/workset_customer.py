"""Customer onboarding and management for multi-tenant workset system.

Handles customer provisioning, S3 bucket creation, and billing tags.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import datetime as dt
from dataclasses import dataclass, field
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
    is_admin: bool = False
    # API tokens for this customer (stored as a list of maps in DynamoDB)
    # Each token dict contains: id, name, token_hash, created_at, expires_at, revoked
    api_tokens: List[Dict] = field(default_factory=list)


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
        self.customer_table = self.dynamodb.Table(self.customer_table_name)

        # Sanity logging/guards so mis-bound DynamoDB resources surface immediately
        LOGGER.info(
            "CustomerManager bound to table: %s (region=%s)",
            self.customer_table.table_name,
            self.region,
        )
        assert hasattr(self.customer_table, "table_name")

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
        custom_s3_bucket: Optional[str] = None,
    ) -> CustomerConfig:
        """Onboard a new customer with provisioned resources.

        Args:
            customer_name: Customer name
            email: Customer email
            max_concurrent_worksets: Max concurrent worksets allowed
            max_storage_gb: Max storage in GB
            billing_account_id: Optional billing account ID
            cost_center: Optional cost center code
            custom_s3_bucket: Optional customer-provided S3 bucket (BYOB)

        Returns:
            CustomerConfig with provisioned resources
        """
        # Generate unique customer ID
        customer_id = self._generate_customer_id(customer_name)

        # Use custom bucket or create new one
        if custom_s3_bucket:
            bucket_name = custom_s3_bucket
            LOGGER.info(
                "Using customer-provided S3 bucket: %s for customer %s",
                bucket_name,
                customer_id,
            )
        else:
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
            "Onboarded customer %s (ID: %s, bucket: %s, byob: %s)",
            customer_name,
            customer_id,
            bucket_name,
            bool(custom_s3_bucket),
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
            # Note: boto3 requires "ID" (uppercase), not "Id"
            lifecycle_policy = {
                "Rules": [
                    {
                        "ID": "DeleteOldWorksets",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "worksets/"},
                        "Expiration": {"Days": 90},
                    },
                    {
                        "ID": "TransitionToIA",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "results/"},
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
                LOGGER.error("Failed to create bucket %s: %s", bucket_name, str(e))
                raise

    def _save_customer_config(self, config: CustomerConfig) -> None:
        """Save customer configuration to DynamoDB.

        Args:
            config: Customer configuration
        """
        # Ensure the customer table exists before saving
        self.create_customer_table_if_not_exists()
        table = self.dynamodb.Table(self.customer_table_name)

        item = {
            "customer_id": config.customer_id,
            "customer_name": config.customer_name,
            "email": config.email,
            "s3_bucket": config.s3_bucket,
            "max_concurrent_worksets": config.max_concurrent_worksets,
            "max_storage_gb": config.max_storage_gb,
            "is_admin": config.is_admin,
        }

        if config.billing_account_id:
            item["billing_account_id"] = config.billing_account_id
        if config.cost_center:
            item["cost_center"] = config.cost_center

        # Persist API tokens if present
        if getattr(config, "api_tokens", None):
            item["api_tokens"] = config.api_tokens

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
                is_admin=item.get("is_admin", False),
                api_tokens=item.get("api_tokens", []),
            )

        except ClientError as e:
            LOGGER.error("Failed to get customer config: %s", str(e))
            return None

    def get_customer_by_email(self, email: str) -> Optional[CustomerConfig]:
        """Get customer configuration by email.

        Args:
            email: Customer email

        Returns:
            CustomerConfig or None if not found
        """
        # Scan for customer with matching email
        # In production, consider adding a GSI on email
        LOGGER.debug(f"get_customer_by_email: Looking for email: '{email}'")
        customers = self.list_customers()
        LOGGER.debug(f"get_customer_by_email: Found {len(customers)} customers")
        for customer in customers:
            LOGGER.debug(f"get_customer_by_email: Comparing customer.email='{customer.email}' (lower='{customer.email.lower()}') with search_email='{email}' (lower='{email.lower()}')")
            if customer.email.lower() == email.lower():
                LOGGER.debug(f"get_customer_by_email: MATCH FOUND! customer_id={customer.customer_id}")
                return customer
        LOGGER.warning(f"get_customer_by_email: No matching customer found for email: '{email}'. Available emails: {[c.email for c in customers]}")
        return None

    def set_admin_status(self, email: str, is_admin: bool) -> bool:
        """Set admin status for a customer by email.

        Args:
            email: Customer email
            is_admin: Whether user should be admin

        Returns:
            True if successful, False otherwise
        """
        customer = self.get_customer_by_email(email)
        if not customer:
            LOGGER.error("Customer with email %s not found", email)
            return False

        # Update the config
        customer.is_admin = is_admin
        self._save_customer_config(customer)
        LOGGER.info("Set admin status for %s (%s) to %s", customer.customer_name, email, is_admin)
        return True

    def list_customers(self) -> List[CustomerConfig]:
        """List all customers.

        Returns:
            List of CustomerConfig objects
        """
        table = self.dynamodb.Table(self.customer_table_name)

        try:
            response = table.scan()
            items = response.get("Items", [])
            LOGGER.debug(f"list_customers: Scanned {len(items)} items from DynamoDB")

            customers = []
            for item in items:
                LOGGER.debug(
                    "list_customers: Processing item with customer_id=%s, email=%s",
                    item.get("customer_id"),
                    item.get("email"),
                )
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
                        is_admin=item.get("is_admin", False),
                        api_tokens=item.get("api_tokens", []),
                    )
                )

            LOGGER.debug(f"list_customers: Returning {len(customers)} customers")
            return customers

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                LOGGER.warning(
                    "Customer table %s not found when listing customers; attempting to create it",
                    self.customer_table_name,
                )
                try:
                    self.create_customer_table_if_not_exists()
                except Exception as create_err:  # pragma: no cover - defensive logging
                    # Avoid logging the raw exception object to prevent deepcopy recursion issues
                    LOGGER.error(
                        "Failed to create customer table %s after ResourceNotFoundException: %s",
                        self.customer_table_name,
                        str(create_err),
                    )
                # No customers yet; return empty list
                return []

            LOGGER.error("Failed to list customers: %s", str(e))
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
            import datetime as dt
            cloudwatch = boto3.client("cloudwatch", region_name=self.region)

            # Get bucket size metric (this is updated daily by AWS)
            # Use dynamic date range: last 7 days to today
            end_time = dt.datetime.now(dt.timezone.utc)
            start_time = end_time - dt.timedelta(days=7)

            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": config.s3_bucket},
                    {"Name": "StorageType", "Value": "StandardStorage"},
                ],
                StartTime=start_time.isoformat(),
                EndTime=end_time.isoformat(),
                Period=86400,
                Statistics=["Average"],
            )

            datapoints = response.get("Datapoints", [])
            storage_bytes = datapoints[-1]["Average"] if datapoints else 0
            storage_gb = storage_bytes / (1024 ** 3)

        except Exception as e:
            LOGGER.warning("Failed to get storage metrics: %s", str(e))
            storage_gb = 0

        # Convert Decimal to float for calculations (DynamoDB returns Decimals)
        max_storage_gb = float(config.max_storage_gb) if config.max_storage_gb else 0

        return {
            "customer_id": customer_id,
            "storage_gb": round(storage_gb, 2),
            "max_storage_gb": max_storage_gb,
            "storage_utilization_percent": round(
                (storage_gb / max_storage_gb) * 100, 2
            ) if max_storage_gb > 0 else 0,
        }

    # ==================================================================
    # API Token Management
    # ==================================================================

    def list_api_tokens(self, customer_id: str) -> List[Dict]:
        """List API tokens for a customer.

        Returns only metadata (no secret or token_hash).
        """
        config = self.get_customer_config(customer_id)
        if not config:
            return []

        tokens = getattr(config, "api_tokens", []) or []
        result: List[Dict] = []
        for token in tokens:
            result.append(
                {
                    "id": token.get("id"),
                    "name": token.get("name"),
                    "created_at": token.get("created_at"),
                    "expires_at": token.get("expires_at"),
                    "revoked": bool(token.get("revoked", False)),
                }
            )
        return result

    def add_api_token(self, customer_id: str, name: str, expiry_days: int) -> Dict:
        """Create a new API token for a customer.

        Returns a dict with ``secret`` (token string) and ``token`` (metadata).
        """
        config = self.get_customer_config(customer_id)
        if not config:
            raise ValueError(f"Customer {customer_id} not found")

        now = dt.datetime.now(dt.timezone.utc)
        created_at = now.isoformat().replace("+00:00", "Z")
        expires_at: Optional[str] = None
        if expiry_days and expiry_days > 0:
            expires_at = (now + dt.timedelta(days=expiry_days)).isoformat() + "Z"

        token_id = secrets.token_hex(8)
        secret = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()

        token_record = {
            "id": token_id,
            "name": name,
            "token_hash": token_hash,
            "created_at": created_at,
            "expires_at": expires_at,
            "revoked": False,
        }

        tokens = list(getattr(config, "api_tokens", []) or [])
        tokens.append(token_record)
        config.api_tokens = tokens
        self._save_customer_config(config)

        public_token = {
            "id": token_id,
            "name": name,
            "created_at": created_at,
            "expires_at": expires_at,
            "revoked": False,
        }
        return {"secret": secret, "token": public_token}

    def revoke_api_token(self, customer_id: str, token_id: str) -> bool:
        """Revoke an API token for a customer.

        Marks the token as revoked but keeps it in the list for auditability.
        """
        config = self.get_customer_config(customer_id)
        if not config or not getattr(config, "api_tokens", None):
            return False

        changed = False
        for token in config.api_tokens:
            if token.get("id") == token_id and not token.get("revoked", False):
                token["revoked"] = True
                changed = True

        if changed:
            self._save_customer_config(config)

        return changed

    def get_customer_by_api_key(self, api_key: str) -> Optional[CustomerConfig]:
        """Resolve a customer by API key string.

        Looks up all customers for a matching token hash that is not revoked and
        (if set) not expired. Intended for low-volume administrative/API use.
        """
        if not api_key:
            return None

        token_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        now = dt.datetime.now(dt.timezone.utc)

        for customer in self.list_customers():
            tokens = getattr(customer, "api_tokens", []) or []
            for token in tokens:
                if token.get("revoked", False):
                    continue
                expires_at = token.get("expires_at")
                if expires_at:
                    try:
                        exp_dt = dt.datetime.fromisoformat(expires_at.replace("Z", ""))
                        if exp_dt < now:
                            continue
                    except Exception:
                        # If we can't parse expiry, ignore it rather than failing auth
                        pass

                if token.get("token_hash") == token_hash:
                    return customer

        return None
