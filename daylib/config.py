"""Centralized configuration management for Daylily.

Uses Pydantic BaseSettings for environment variable loading with validation.
Configuration is loaded once at startup and injected via dependency.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Daylily application settings.

    All settings can be overridden via environment variables.
    Environment variable names are uppercase versions of the field names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========== AWS Configuration ==========
    aws_default_region: str = Field(
        default="us-west-2",
        description="AWS region for all services",
    )
    aws_profile: Optional[str] = Field(
        default=None,
        description="AWS profile name (None uses default credentials chain)",
    )
    aws_account_id: Optional[str] = Field(
        default=None,
        description="AWS account ID for resource ARNs",
    )

    # ========== DynamoDB Table Names ==========
    workset_table_name: str = Field(
        default="daylily-worksets",
        description="DynamoDB table for workset state",
    )
    customer_table_name: str = Field(
        default="daylily-customers",
        description="DynamoDB table for customer configuration",
    )
    daylily_manifest_table: str = Field(
        default="daylily-manifests",
        description="DynamoDB table for manifest storage",
    )
    daylily_linked_buckets_table: str = Field(
        default="daylily-linked-buckets",
        description="DynamoDB table for linked bucket management",
    )
    daylily_file_registry_table: str = Field(
        default="daylily-file-registry",
        description="DynamoDB table for file registry",
    )

    # ========== S3 Configuration ==========
    daylily_control_bucket: Optional[str] = Field(
        default=None,
        description="S3 bucket for control plane data (worksets, configs)",
    )
    daylily_monitor_bucket: Optional[str] = Field(
        default=None,
        description="S3 bucket for monitoring (legacy alias for control bucket)",
    )
    s3_bucket: Optional[str] = Field(
        default=None,
        description="Default S3 bucket for workset data",
    )
    s3_prefix: str = Field(
        default="worksets/",
        description="Default S3 prefix for workset data",
    )

    # ========== Authentication ==========
    cognito_user_pool_id: Optional[str] = Field(
        default=None,
        description="AWS Cognito User Pool ID",
    )
    cognito_app_client_id: Optional[str] = Field(
        default=None,
        description="AWS Cognito App Client ID",
    )
    enable_auth: bool = Field(
        default=False,
        description="Enable authentication (requires Cognito configuration)",
    )
    session_secret_key: str = Field(
        default="daylily-dev-secret-change-in-production",
        description="Secret key for session encryption (CHANGE IN PRODUCTION)",
    )

    # ========== CORS Configuration ==========
    cors_origins: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins (* for all)",
    )
    daylily_env: str = Field(
        default="development",
        description="Environment: development, staging, production",
    )

    # ========== Demo Mode ==========
    demo_mode: bool = Field(
        default=False,
        description="Enable demo mode (allows first-customer fallback). NEVER enable in production.",
    )

    # ========== API Server ==========
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host",
    )
    api_port: int = Field(
        default=8001,
        description="API server port",
    )

    # ========== Notifications ==========
    sns_topic_arn: Optional[str] = Field(
        default=None,
        description="SNS topic ARN for notifications",
    )
    daylily_sns_topic_arn: Optional[str] = Field(
        default=None,
        description="Daylily-specific SNS topic ARN",
    )
    linear_api_key: Optional[str] = Field(
        default=None,
        description="Linear API key for issue tracking integration",
    )
    linear_team_id: Optional[str] = Field(
        default=None,
        description="Linear team ID for issue tracking",
    )

    # ========== Daylily Project Config ==========
    day_project: Optional[str] = Field(default=None, description="Daylily project name")
    day_aws_region: Optional[str] = Field(default=None, description="Daylily AWS region override")
    day_ex_cfg: Optional[str] = Field(default=None, description="Daylily execution config")
    daylily_primary_region: Optional[str] = Field(default=None, description="Primary region for multi-region")
    daylily_multi_region: bool = Field(default=False, description="Enable multi-region support")
    day_biome: Optional[str] = Field(default=None, description="Daylily biome setting")
    day_root: Optional[str] = Field(default=None, description="Daylily root directory")
    apptainer_home: Optional[str] = Field(default=None, description="Apptainer home directory")

    # ========== Logging ==========
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )

    # ========== Rate Limiting ==========
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
    )
    rate_limit_auth_per_minute: int = Field(
        default=10,
        description="Rate limit for auth endpoints (requests per minute per IP)",
    )
    rate_limit_read_per_minute: int = Field(
        default=100,
        description="Rate limit for read endpoints (requests per minute per user)",
    )
    rate_limit_write_per_minute: int = Field(
        default=30,
        description="Rate limit for write endpoints (requests per minute per user)",
    )
    rate_limit_admin_per_minute: int = Field(
        default=20,
        description="Rate limit for admin endpoints (requests per minute per user)",
    )
    rate_limit_storage_uri: Optional[str] = Field(
        default=None,
        description="Redis URI for rate limit storage (None = in-memory)",
    )
    rate_limit_whitelist: str = Field(
        default="",
        description="Comma-separated list of whitelisted IPs or user IDs",
    )

    # ========== Validation ==========
    validation_strictness: str = Field(
        default="strict",
        description="Validation strictness level: strict, permissive",
    )
    validation_required: bool = Field(
        default=True,
        description="Require validation for workset creation/updates",
    )

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_in_production(cls, v: str, info) -> str:
        """Warn if wildcard CORS is used in production."""
        # Note: We can't access other fields in field_validator easily,
        # so production check is done at runtime in get_cors_origins()
        return v

    @field_validator("daylily_env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the allowed values."""
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"daylily_env must be one of: {allowed}")
        return v.lower()

    def get_cors_origins(self) -> List[str]:
        """Get list of CORS origins from comma-separated string.

        Raises ValueError if wildcard is used in production.
        """
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if self.daylily_env == "production" and "*" in origins:
            raise ValueError(
                "Wildcard CORS origin (*) is not allowed in production. "
                "Set CORS_ORIGINS to a comma-separated list of allowed origins."
            )
        return origins

    def get_control_bucket(self) -> Optional[str]:
        """Get control bucket, preferring DAYLILY_CONTROL_BUCKET over legacy DAYLILY_MONITOR_BUCKET."""
        return self.daylily_control_bucket or self.daylily_monitor_bucket

    def get_effective_region(self) -> str:
        """Get the effective AWS region, considering overrides."""
        return self.day_aws_region or self.aws_default_region

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.daylily_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.daylily_env == "development"

    def validate_demo_mode(self) -> None:
        """Validate demo mode is not enabled in production.

        Raises:
            ValueError: If demo_mode is True in production environment.
        """
        if self.demo_mode and self.is_production:
            raise ValueError(
                "Demo mode (DEMO_MODE=true) is not allowed in production. "
                "Set DAYLILY_ENV to 'development' or 'staging' to use demo mode, "
                "or disable demo mode by setting DEMO_MODE=false."
            )

    @property
    def auth_configured(self) -> bool:
        """Check if authentication is properly configured."""
        return bool(self.cognito_user_pool_id and self.cognito_app_client_id)

    def get_rate_limit_whitelist(self) -> List[str]:
        """Get list of whitelisted IPs/user IDs for rate limiting."""
        if not self.rate_limit_whitelist:
            return []
        return [w.strip() for w in self.rate_limit_whitelist.split(",") if w.strip()]

    def is_rate_limit_whitelisted(self, identifier: str) -> bool:
        """Check if an identifier (IP or user ID) is whitelisted."""
        return identifier in self.get_rate_limit_whitelist()

    @field_validator("validation_strictness")
    @classmethod
    def validate_strictness_level(cls, v: str) -> str:
        """Validate strictness level is one of the allowed values."""
        allowed = {"strict", "permissive"}
        if v.lower() not in allowed:
            raise ValueError(f"validation_strictness must be one of: {allowed}")
        return v.lower()

    @property
    def is_validation_strict(self) -> bool:
        """Check if validation is in strict mode."""
        return self.validation_strictness == "strict"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    Use this function as a FastAPI dependency.
    """
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache.

    Useful for testing when you need to reload settings with different
    environment variables.
    """
    get_settings.cache_clear()


def get_settings_for_testing(**overrides) -> Settings:
    """Create settings instance with overrides for testing.

    This bypasses the cache, allowing tests to use custom configuration.
    """
    return Settings(**overrides)

