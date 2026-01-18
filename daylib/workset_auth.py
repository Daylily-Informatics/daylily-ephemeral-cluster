"""AWS Cognito authentication for workset API.

Provides JWT token validation and user management for multi-tenant access.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

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
                    pool_id: str = str(pool["Id"])
                    self.user_pool_id = pool_id
                    self._update_jwks_url()
                    return pool_id

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

            new_pool_id: str = str(response["UserPool"]["Id"])
            LOGGER.info("Created user pool %s", new_pool_id)
            # Update instance to use this pool
            self.user_pool_id = new_pool_id
            self._update_jwks_url()
            return new_pool_id

        except ClientError as e:
            LOGGER.error("Failed to create user pool: %s", str(e))
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
                    existing_client_id: str = str(client["ClientId"])
                    LOGGER.info("App client %s already exists: %s", client_name, existing_client_id)
                    self.app_client_id = existing_client_id
                    return existing_client_id

            # Create new client
            response = self.cognito.create_user_pool_client(
                UserPoolId=self.user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_ADMIN_USER_PASSWORD_AUTH",  # Required for admin_initiate_auth
                    "ALLOW_REFRESH_TOKEN_AUTH",
                ],
                ReadAttributes=["email", "custom:customer_id"],
                WriteAttributes=["email"],
            )

            new_client_id: str = str(response["UserPoolClient"]["ClientId"])
            LOGGER.info("Created app client %s", new_client_id)
            # Update instance to use this client
            self.app_client_id = new_client_id
            return new_client_id

        except ClientError as e:
            LOGGER.error("Failed to create app client: %s", str(e))
            raise

    def update_app_client_auth_flows(self) -> None:
        """Update existing app client to enable required auth flows.

        This is useful for fixing existing app clients that were created
        without ALLOW_ADMIN_USER_PASSWORD_AUTH enabled.
        """
        if not self.user_pool_id or not self.app_client_id:
            raise ValueError("user_pool_id and app_client_id must be set")

        try:
            # Get current client configuration
            response = self.cognito.describe_user_pool_client(
                UserPoolId=self.user_pool_id,
                ClientId=self.app_client_id,
            )
            client_config = response["UserPoolClient"]

            # Update with required auth flows
            self.cognito.update_user_pool_client(
                UserPoolId=self.user_pool_id,
                ClientId=self.app_client_id,
                ClientName=client_config["ClientName"],
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                ],
                ReadAttributes=client_config.get("ReadAttributes", ["email", "custom:customer_id"]),
                WriteAttributes=client_config.get("WriteAttributes", ["email"]),
            )
            LOGGER.info(f"Updated app client {self.app_client_id} with required auth flows")

        except ClientError as e:
            LOGGER.error(f"Failed to update app client: {e}")
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
            user_data: Dict[Any, Any] = dict(response["User"])
            return user_data

        except ClientError as e:
            if e.response["Error"]["Code"] == "UsernameExistsException":
                LOGGER.warning("User %s already exists", email)
                raise ValueError(f"User {email} already exists")
            LOGGER.error("Failed to create user: %s", str(e))
            raise

    def verify_token(self, token: str) -> Dict[Any, Any]:
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
            claims: Dict[Any, Any] = jwt.decode(
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
            LOGGER.error("JWT validation error: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

    def get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> Dict:
        """FastAPI dependency to get current authenticated user.

        Args:
            credentials: HTTP bearer credentials (may be None if not provided)

        Returns:
            User claims dict

        Raises:
            HTTPException: If credentials are not provided or invalid
        """
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
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
        return str(customer_id)

    def list_customer_users(self, customer_id: str) -> List[Dict[Any, Any]]:
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

            users: List[Dict[Any, Any]] = list(response.get("Users", []))
            return users

        except ClientError as e:
            LOGGER.error("Failed to list users for customer %s: %s", customer_id, str(e))
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
            LOGGER.error("Failed to delete user %s: %s", email, str(e))
            return False

    def authenticate(self, email: str, password: str) -> Dict:
        """Authenticate a user with email and password.

        Args:
            email: User email
            password: User password

        Returns:
            Dict containing authentication tokens (AccessToken, IdToken, RefreshToken)

        Raises:
            ValueError: If authentication fails (invalid credentials)
            ClientError: If there's an AWS API error
        """
        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.app_client_id,
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                },
            )

            # Check if challenge is required (e.g., NEW_PASSWORD_REQUIRED)
            if "ChallengeName" in response:
                challenge_name = response["ChallengeName"]
                LOGGER.warning(
                    "Authentication challenge required for user %s: %s",
                    email,
                    challenge_name,
                )

                # Return challenge info so caller can handle it
                return {
                    "challenge": challenge_name,
                    "session": response.get("Session"),
                    "challenge_parameters": response.get("ChallengeParameters", {}),
                }

            # Extract tokens
            auth_result = response.get("AuthenticationResult", {})
            if not auth_result:
                raise ValueError("Authentication failed: No tokens returned")

            LOGGER.info("User %s authenticated successfully", email)
            return {
                "access_token": auth_result.get("AccessToken"),
                "id_token": auth_result.get("IdToken"),
                "refresh_token": auth_result.get("RefreshToken"),
                "expires_in": auth_result.get("ExpiresIn"),
                "token_type": auth_result.get("TokenType", "Bearer"),
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NotAuthorizedException":
                LOGGER.warning("Authentication failed for user %s: Invalid credentials", email)
                raise ValueError("Invalid email or password")
            elif error_code == "UserNotFoundException":
                LOGGER.warning("Authentication failed for user %s: User not found", email)
                raise ValueError("Invalid email or password")
            elif error_code == "UserNotConfirmedException":
                LOGGER.warning("Authentication failed for user %s: User not confirmed", email)
                raise ValueError("User account not confirmed")
            else:
                LOGGER.error("Authentication error for user %s: %s - %s", email, error_code, error_message)
                raise

    def respond_to_new_password_challenge(
        self,
        email: str,
        new_password: str,
        session: str
    ) -> Dict:
        """Respond to NEW_PASSWORD_REQUIRED challenge.

        This is used when a user logs in with a temporary password and must
        set a new password before continuing.

        Args:
            email: User email
            new_password: New password to set
            session: Session token from the challenge response

        Returns:
            Dict containing authentication tokens

        Raises:
            ValueError: If the challenge response fails
        """
        try:
            response = self.cognito.admin_respond_to_auth_challenge(
                UserPoolId=self.user_pool_id,
                ClientId=self.app_client_id,
                ChallengeName="NEW_PASSWORD_REQUIRED",
                ChallengeResponses={
                    "USERNAME": email,
                    "NEW_PASSWORD": new_password,
                },
                Session=session,
            )

            # Extract tokens
            auth_result = response.get("AuthenticationResult", {})
            if not auth_result:
                raise ValueError("Password change failed: No tokens returned")

            LOGGER.info(f"User {email} successfully changed password and authenticated")
            return {
                "access_token": auth_result.get("AccessToken"),
                "id_token": auth_result.get("IdToken"),
                "refresh_token": auth_result.get("RefreshToken"),
                "expires_in": auth_result.get("ExpiresIn"),
                "token_type": auth_result.get("TokenType", "Bearer"),
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            LOGGER.error(f"Password change challenge failed for {email}: {error_code} - {error_message}")

            if error_code == "InvalidPasswordException":
                raise ValueError("Password does not meet requirements")
            else:
                raise ValueError(f"Password change failed: {error_message}")

    def forgot_password(self, email: str) -> None:
        """Initiate forgot password flow for a user.

        Sends a verification code to the user's email address.

        Args:
            email: User's email address

        Raises:
            ValueError: If the request fails
        """
        try:
            self.cognito.forgot_password(
                ClientId=self.app_client_id,
                Username=email,
            )
            LOGGER.info(f"Password reset code sent to {email}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            LOGGER.error(f"Forgot password error for user {email}: {error_code} - {error_message}")

            # Map AWS errors to user-friendly messages
            if error_code == "UserNotFoundException":
                # Don't reveal if user exists or not for security
                LOGGER.warning(f"Password reset requested for non-existent user: {email}")
                # Still return success to avoid user enumeration
                return
            elif error_code == "InvalidParameterException":
                raise ValueError("Invalid request parameters")
            elif error_code == "LimitExceededException":
                raise ValueError("Too many requests. Please try again later")
            else:
                raise ValueError(f"Password reset failed: {error_message}")

    def confirm_forgot_password(self, email: str, confirmation_code: str, new_password: str) -> None:
        """Confirm forgot password with verification code and set new password.

        Args:
            email: User's email address
            confirmation_code: Verification code sent to user's email
            new_password: New password to set

        Raises:
            ValueError: If the confirmation fails
        """
        try:
            self.cognito.confirm_forgot_password(
                ClientId=self.app_client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
                Password=new_password,
            )
            LOGGER.info(f"Password reset successful for {email}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            LOGGER.error(f"Confirm forgot password error for user {email}: {error_code} - {error_message}")

            # Map AWS errors to user-friendly messages
            if error_code == "CodeMismatchException":
                raise ValueError("Invalid verification code")
            elif error_code == "ExpiredCodeException":
                raise ValueError("Verification code has expired. Please request a new one")
            elif error_code == "InvalidPasswordException":
                raise ValueError("Password does not meet requirements")
            elif error_code == "UserNotFoundException":
                raise ValueError("User not found")
            else:
                raise ValueError(f"Password reset failed: {error_message}")

    def change_password(self, access_token: str, old_password: str, new_password: str) -> None:
        """Change password for authenticated user.

        Args:
            access_token: User's access token
            old_password: Current password
            new_password: New password to set

        Raises:
            ValueError: If the password change fails
        """
        try:
            self.cognito.change_password(
                AccessToken=access_token,
                PreviousPassword=old_password,
                ProposedPassword=new_password,
            )
            LOGGER.info("Password changed successfully")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            LOGGER.error(f"Change password error: {error_code} - {error_message}")

            # Map AWS errors to user-friendly messages
            if error_code == "NotAuthorizedException":
                raise ValueError("Current password is incorrect")
            elif error_code == "InvalidPasswordException":
                raise ValueError("Password does not meet requirements")
            elif error_code == "InvalidParameterException":
                raise ValueError("Invalid request parameters")
            else:
                raise ValueError(f"Password change failed: {error_message}")


def create_auth_dependency(cognito_auth: CognitoAuth, optional: bool = False):
    """Create FastAPI dependency for authentication.

    Args:
        cognito_auth: CognitoAuth instance
        optional: If True, returns None when no credentials provided instead of raising error

    Returns:
        Dependency function
    """
    def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> Optional[Dict]:
        if credentials is None:
            if optional:
                return None
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return cognito_auth.get_current_user(credentials)

    return get_current_user

