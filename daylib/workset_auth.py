"""AWS Cognito authentication for workset API.

Provides JWT token validation and user management for multi-tenant access.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Optional jose import - only needed if authentication is enabled
try:
    from jose import JWTError, jwt
    JOSE_AVAILABLE = True
except (ImportError, SyntaxError) as e:
    # ImportError: python-jose not installed
    # SyntaxError: wrong 'jose' package installed (need python-jose)
    JOSE_AVAILABLE = False
    JWTError = Exception  # Fallback for type hints
    LOGGER_IMPORT = logging.getLogger("daylily.workset_auth")

    if isinstance(e, SyntaxError):
        LOGGER_IMPORT.warning(
            "Incompatible 'jose' package found. Please uninstall it and install 'python-jose' instead. "
            "Run: pip uninstall jose && pip install 'python-jose[cryptography]'"
        )
    else:
        LOGGER_IMPORT.warning(
            "python-jose not installed. Authentication features will be disabled. "
            "Install with: pip install 'python-jose[cryptography]'"
        )

LOGGER = logging.getLogger("daylily.workset_auth")

security = HTTPBearer(auto_error=False)


class CognitoAuth:
    """AWS Cognito authentication handler.

    Note: Requires python-jose to be installed for JWT validation.
    Install with: pip install 'python-jose[cryptography]'

    Usage:
        # Option 1: Use existing pool and client
        auth = CognitoAuth(
            region="us-west-2",
            user_pool_id="us-west-2_XXXXXXXXX",
            app_client_id="XXXXXXXXXXXXXXXXXXXXXXXXXX",
        )

        # Option 2: Create new pool and client automatically
        auth = CognitoAuth.create_with_new_pool(region="us-west-2")
        print(f"Pool ID: {auth.user_pool_id}")
        print(f"Client ID: {auth.app_client_id}")
    """

    def __init__(
        self,
        region: str,
        user_pool_id: str = "",
        app_client_id: str = "",
        profile: Optional[str] = None,
    ):
        """Initialize Cognito auth.

        Args:
            region: AWS region
            user_pool_id: Cognito User Pool ID (can be empty if using create_user_pool_if_not_exists)
            app_client_id: Cognito App Client ID (can be empty if using create_app_client)
            profile: AWS profile name

        Raises:
            ImportError: If python-jose is not installed
        """
        if not JOSE_AVAILABLE:
            raise ImportError(
                "python-jose is required for authentication. "
                "Install with: pip install 'python-jose[cryptography]'"
            )

        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.cognito = session.client("cognito-idp")
        self.region = region
        self.user_pool_id = user_pool_id
        self.app_client_id = app_client_id
        self.profile = profile

        # Get JWKS for token validation (will be empty URL if no pool_id yet)
        self.jwks_url = ""
        if user_pool_id:
            self._update_jwks_url()

    @classmethod
    def create_with_new_pool(
        cls,
        region: str,
        pool_name: str = "daylily-workset-users",
        client_name: str = "daylily-workset-api",
        profile: Optional[str] = None,
    ) -> "CognitoAuth":
        """Create a CognitoAuth instance with a new user pool and app client.

        This is a convenience method that creates the user pool and app client
        if they don't exist, and returns a fully configured CognitoAuth instance.

        Args:
            region: AWS region
            pool_name: Name for the user pool
            client_name: Name for the app client
            profile: AWS profile name

        Returns:
            Fully configured CognitoAuth instance

        Example:
            auth = CognitoAuth.create_with_new_pool(region="us-west-2")
            print(f"Pool ID: {auth.user_pool_id}")
            print(f"Client ID: {auth.app_client_id}")
        """
        # Create instance with empty IDs
        auth = cls(region=region, user_pool_id="", app_client_id="", profile=profile)

        # Create or get user pool (updates self.user_pool_id)
        auth.create_user_pool_if_not_exists(pool_name=pool_name)

        # Create app client (updates self.app_client_id)
        auth.create_app_client(client_name=client_name)

        return auth

    def create_user_pool_if_not_exists(
        self,
        pool_name: str = "daylily-workset-users",
    ) -> str:
        """Create Cognito User Pool if it doesn't exist.

        Args:
            pool_name: User pool name

        Returns:
            User pool ID

        Note:
            This method updates self.user_pool_id with the created/found pool ID.
        """
        try:
            # Check if pool exists
            response = self.cognito.list_user_pools(MaxResults=60)
            for pool in response.get("UserPools", []):
                if pool["Name"] == pool_name:
                    LOGGER.info("User pool %s already exists", pool_name)
                    # Update instance to use this pool
                    self.user_pool_id = pool["Id"]
                    self._update_jwks_url()
                    return pool["Id"]

            # Create new pool
            LOGGER.info("Creating user pool %s", pool_name)
            response = self.cognito.create_user_pool(
                PoolName=pool_name,
                Policies={
                    "PasswordPolicy": {
                        "MinimumLength": 8,
                        "RequireUppercase": True,
                        "RequireLowercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": False,
                    }
                },
                AutoVerifiedAttributes=["email"],
                UsernameAttributes=["email"],
                Schema=[
                    {
                        "Name": "email",
                        "AttributeDataType": "String",
                        "Required": True,
                        "Mutable": True,
                    },
                    {
                        "Name": "customer_id",
                        "AttributeDataType": "String",
                        "Mutable": True,
                    },
                ],
            )

            pool_id = response["UserPool"]["Id"]
            LOGGER.info("Created user pool %s", pool_id)
            # Update instance to use this pool
            self.user_pool_id = pool_id
            self._update_jwks_url()
            return pool_id

        except ClientError as e:
            LOGGER.error("Failed to create user pool: %s", e)
            raise

    def _update_jwks_url(self) -> None:
        """Update JWKS URL after user_pool_id changes."""
        self.jwks_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/"
            f"{self.user_pool_id}/.well-known/jwks.json"
        )

    def create_app_client(
        self,
        client_name: str = "daylily-workset-api",
    ) -> str:
        """Create Cognito App Client.

        Args:
            client_name: App client name

        Returns:
            App client ID

        Note:
            This method updates self.app_client_id with the created client ID.
        """
        if not self.user_pool_id:
            raise ValueError(
                "user_pool_id is not set. Call create_user_pool_if_not_exists() first "
                "or provide user_pool_id when initializing CognitoAuth."
            )

        try:
            # First check if client already exists
            response = self.cognito.list_user_pool_clients(
                UserPoolId=self.user_pool_id,
                MaxResults=60,
            )
            for client in response.get("UserPoolClients", []):
                if client["ClientName"] == client_name:
                    LOGGER.info("App client %s already exists: %s", client_name, client["ClientId"])
                    self.app_client_id = client["ClientId"]
                    return client["ClientId"]

            # Create new client
            response = self.cognito.create_user_pool_client(
                UserPoolId=self.user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                ],
                ReadAttributes=["email", "custom:customer_id"],
                WriteAttributes=["email"],
            )

            client_id = response["UserPoolClient"]["ClientId"]
            LOGGER.info("Created app client %s", client_id)
            # Update instance to use this client
            self.app_client_id = client_id
            return client_id

        except ClientError as e:
            LOGGER.error("Failed to create app client: %s", e)
            raise

    def create_customer_user(
        self,
        email: str,
        customer_id: str,
        temporary_password: Optional[str] = None,
    ) -> Dict:
        """Create a new customer user.

        Args:
            email: User email
            customer_id: Customer identifier
            temporary_password: Optional temporary password

        Returns:
            User details dict
        """
        try:
            kwargs = {
                "UserPoolId": self.user_pool_id,
                "Username": email,
                "UserAttributes": [
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "custom:customer_id", "Value": customer_id},
                ],
                "DesiredDeliveryMediums": ["EMAIL"],
            }

            if temporary_password:
                kwargs["TemporaryPassword"] = temporary_password

            response = self.cognito.admin_create_user(**kwargs)

            LOGGER.info("Created user %s for customer %s", email, customer_id)
            return response["User"]

        except ClientError as e:
            if e.response["Error"]["Code"] == "UsernameExistsException":
                LOGGER.warning("User %s already exists", email)
                raise ValueError(f"User {email} already exists")
            LOGGER.error("Failed to create user: %s", e)
            raise

    def verify_token(self, token: str) -> Dict:
        """Verify JWT token from Cognito.

        Args:
            token: JWT token string

        Returns:
            Decoded token claims

        Raises:
            HTTPException if token is invalid
        """
        try:
            # Decode without verification first to get header
            unverified_header = jwt.get_unverified_header(token)

            # In production, fetch and cache JWKS keys
            # For now, decode with basic validation
            claims = jwt.decode(
                token,
                options={"verify_signature": False},  # TODO: Implement proper JWKS verification
            )

            # Verify token hasn't expired
            if "exp" in claims:
                import time
                if claims["exp"] < time.time():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired",
                    )

            # Verify audience (app client ID)
            if claims.get("client_id") != self.app_client_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token audience",
                )

            return claims

        except JWTError as e:
            LOGGER.error("JWT validation error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

    def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> Dict:
        """FastAPI dependency to get current authenticated user.

        Args:
            credentials: HTTP bearer credentials

        Returns:
            User claims dict
        """
        token = credentials.credentials
        return self.verify_token(token)

    def get_customer_id(self, user_claims: Dict) -> str:
        """Extract customer ID from user claims.

        Args:
            user_claims: Decoded JWT claims

        Returns:
            Customer ID

        Raises:
            HTTPException if customer_id not found
        """
        customer_id = user_claims.get("custom:customer_id")
        if not customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not associated with a customer",
            )
        return customer_id

    def list_customer_users(self, customer_id: str) -> List[Dict]:
        """List all users for a customer.

        Args:
            customer_id: Customer identifier

        Returns:
            List of user dicts
        """
        try:
            response = self.cognito.list_users(
                UserPoolId=self.user_pool_id,
                Filter=f'custom:customer_id = "{customer_id}"',
            )

            return response.get("Users", [])

        except ClientError as e:
            LOGGER.error("Failed to list users for customer %s: %s", customer_id, e)
            return []

    def delete_user(self, email: str) -> bool:
        """Delete a user.

        Args:
            email: User email

        Returns:
            True if successful
        """
        try:
            self.cognito.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=email,
            )
            LOGGER.info("Deleted user %s", email)
            return True

        except ClientError as e:
            LOGGER.error("Failed to delete user %s: %s", email, e)
            return False


def create_auth_dependency(cognito_auth: CognitoAuth):
    """Create FastAPI dependency for authentication.

    Args:
        cognito_auth: CognitoAuth instance

    Returns:
        Dependency function
    """
    def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> Dict:
        return cognito_auth.get_current_user(credentials)

    return get_current_user

