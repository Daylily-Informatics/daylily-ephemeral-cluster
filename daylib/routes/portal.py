"""Portal routes for Daylily customer web interface.

Contains HTML template-based routes for:
- Authentication (login, logout, registration, password management)
- Dashboard
- Worksets management
- Files management
- Usage/billing
- Biospecimen management
- Account settings
- Documentation and support
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import boto3
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from daylib.config import Settings
from daylib.routes.dependencies import (
    convert_customer_for_template,
    format_file_size,
    get_file_icon,
    PortalFileAutoRegisterRequest,
    PortalFileAutoRegisterResponse,
)
from daylib.workset_state_db import WorksetStateDB, WorksetState

if TYPE_CHECKING:
    from daylib.workset_auth import CognitoAuth
    from daylib.workset_customer import CustomerManager

LOGGER = logging.getLogger("daylily.routes.portal")


class PortalDependencies:
    """Container for portal route dependencies.

    Encapsulates all external dependencies needed by portal routes,
    making them easier to inject and test.
    """

    def __init__(
        self,
        state_db: WorksetStateDB,
        templates: Jinja2Templates,
        settings: Settings,
        enable_auth: bool = False,
        cognito_auth: Optional["CognitoAuth"] = None,
        customer_manager: Optional["CustomerManager"] = None,
        file_registry: Optional[Any] = None,
        linked_bucket_manager: Optional[Any] = None,
    ):
        self.state_db = state_db
        self.templates = templates
        self.settings = settings
        self.enable_auth = enable_auth
        self.cognito_auth = cognito_auth
        self.customer_manager = customer_manager
        self.file_registry = file_registry
        self.linked_bucket_manager = linked_bucket_manager
        self.region = settings.get_effective_region()
        self.profile = settings.aws_profile


def _get_customer_for_session(request: Request, deps: PortalDependencies):
    """Get the customer for the currently logged-in user.

    Looks up the customer by the user's email from the session.
    Returns (customer, customer_config) tuple or (None, None) if not found.
    """
    if not deps.customer_manager:
        return None, None

    user_email = None
    if hasattr(request, "session"):
        user_email = request.session.get("user_email")

    if not user_email:
        return None, None

    customer_config = deps.customer_manager.get_customer_by_email(user_email)
    if customer_config:
        return convert_customer_for_template(customer_config), customer_config

    return None, None


def _get_template_context(request: Request, deps: PortalDependencies, **kwargs) -> Dict[str, Any]:
    """Build common template context."""
    cache_bust = str(int(datetime.now().timestamp()))
    context = {
        "request": request,
        "auth_enabled": deps.enable_auth,
        "current_year": datetime.now().year,
        "cache_bust": cache_bust,
        **kwargs,
    }
    if "customer" in kwargs and kwargs["customer"]:
        context["customer_id"] = kwargs["customer"].customer_id
    if hasattr(request, "session") and request.session.get("user_email"):
        context["user_email"] = request.session.get("user_email")
        context["user_authenticated"] = True
        context["is_admin"] = request.session.get("is_admin", False)
    return context


def _require_portal_auth(request: Request) -> Optional[RedirectResponse]:
    """Check if user is authenticated for portal access.

    Returns RedirectResponse to login if not authenticated, None if authenticated.
    """
    if not hasattr(request, "session"):
        return RedirectResponse(url="/portal/login", status_code=302)
    if not request.session.get("user_email"):
        return RedirectResponse(url="/portal/login", status_code=302)
    if not request.session.get("customer_id"):
        LOGGER.warning(f"Session missing customer_id for user {request.session.get('user_email')}")
        return RedirectResponse(url="/portal/login", status_code=302)
    return None


def _get_first_customer_converted(deps: PortalDependencies):
    """Helper to get first customer converted for template use."""
    if deps.customer_manager:
        customers = deps.customer_manager.list_customers()
        if customers:
            return convert_customer_for_template(customers[0])
    return None


def create_portal_router(deps: PortalDependencies) -> APIRouter:
    """Create portal router with injected dependencies.

    Args:
        deps: PortalDependencies container with all required dependencies

    Returns:
        Configured APIRouter with portal routes
    """
    router = APIRouter(tags=["portal"])

    # ========== Dashboard ==========

    @router.get("/portal", response_class=HTMLResponse)
    async def portal_dashboard(request: Request):
        """Customer portal dashboard."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect

        customer = None
        customer_id = None
        worksets = []
        stats = {
            "active_worksets": 0,
            "completed_worksets": 0,
            "storage_used_gb": 0,
            "storage_percent": 0,
            "max_storage_gb": 500,
            "cost_this_month": 0,
            "in_progress_worksets": 0,
            "ready_worksets": 0,
            "error_worksets": 0,
            "registered_files": 0,
            "total_file_size_gb": 0,
            "total_file_size_bytes": 0,
        }

        if deps.customer_manager:
            customer, customer_config = _get_customer_for_session(request, deps)
            if customer:
                customer_id = customer.customer_id
            elif deps.settings.demo_mode:
                customers = deps.customer_manager.list_customers()
                if customers:
                    customer_raw = customers[0]
                    customer = convert_customer_for_template(customer_raw)
                    customer_id = customer_raw.customer_id

            if customer_id:
                all_worksets = []
                for ws_state in WorksetState:
                    batch = deps.state_db.list_worksets_by_state(ws_state, limit=100)
                    all_worksets.extend(batch)
                worksets = all_worksets[:10]

                stats["in_progress_worksets"] = len([w for w in all_worksets if w.get("state") == "in_progress"])
                stats["ready_worksets"] = len([w for w in all_worksets if w.get("state") == "ready"])
                stats["completed_worksets"] = len([w for w in all_worksets if w.get("state") == "complete"])
                stats["error_worksets"] = len([w for w in all_worksets if w.get("state") == "error"])
                stats["active_worksets"] = stats["in_progress_worksets"]

                if deps.file_registry:
                    try:
                        customer_files = deps.file_registry.list_customer_files(customer_id, limit=1000)
                        stats["registered_files"] = len(customer_files)
                        total_bytes = sum(f.file_metadata.file_size_bytes for f in customer_files if f.file_metadata)
                        stats["total_file_size_bytes"] = total_bytes
                        stats["total_file_size_gb"] = round(total_bytes / (1024**3), 2)
                    except Exception as e:
                        LOGGER.warning(f"Failed to get file statistics: {e}")

        return deps.templates.TemplateResponse(
            request,
            "dashboard.html",
            _get_template_context(request, deps, customer=customer, worksets=worksets, stats=stats, active_page="dashboard"),
        )

    # ========== Authentication Routes ==========

    @router.get("/portal/login", response_class=HTMLResponse)
    async def portal_login(request: Request, error: Optional[str] = None, success: Optional[str] = None):
        """Login page."""
        return deps.templates.TemplateResponse(
            request,
            "auth/login.html",
            _get_template_context(request, deps, error=error, success=success),
        )

    @router.post("/portal/login")
    async def portal_login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
        """Handle login form submission with proper authentication."""
        LOGGER.debug(f"portal_login_submit: Login attempt for email: {email}")

        if not deps.customer_manager:
            if not deps.enable_auth:
                LOGGER.warning("portal_login_submit: No customer manager; creating demo session for %s", email)
                request.session["user_email"] = email
                request.session["user_authenticated"] = True
                request.session["customer_id"] = "demo-customer"
                request.session["is_admin"] = True
                return RedirectResponse(url="/portal/", status_code=302)
            LOGGER.error("portal_login_submit: Customer manager not configured")
            return RedirectResponse(url="/portal/login?error=Authentication+not+configured", status_code=302)

        customer = deps.customer_manager.get_customer_by_email(email)
        if not customer:
            LOGGER.warning(f"portal_login_submit: Login attempt for non-existent customer: {email}")
            return RedirectResponse(url="/portal/login?error=Invalid+email+or+password", status_code=302)

        if deps.cognito_auth:
            try:
                LOGGER.debug(f"portal_login_submit: Authenticating with Cognito for: {email}")
                auth_result = deps.cognito_auth.authenticate(email, password)

                if "challenge" in auth_result:
                    challenge_name = auth_result["challenge"]
                    LOGGER.info(f"portal_login_submit: Challenge required for {email}: {challenge_name}")
                    if challenge_name == "NEW_PASSWORD_REQUIRED":
                        request.session["challenge_session"] = auth_result["session"]
                        request.session["challenge_email"] = email
                        return RedirectResponse(url="/portal/change-password?reason=temporary", status_code=302)
                    else:
                        LOGGER.error(f"portal_login_submit: Unsupported challenge: {challenge_name}")
                        return RedirectResponse(url=f"/portal/login?error=Authentication+challenge+required:+{challenge_name}", status_code=302)

                request.session["access_token"] = auth_result["access_token"]
                request.session["id_token"] = auth_result["id_token"]
                LOGGER.info(f"portal_login_submit: Cognito authentication successful for: {email}")
            except ValueError as e:
                LOGGER.warning(f"portal_login_submit: Cognito authentication failed for {email}: {e}")
                return RedirectResponse(url="/portal/login?error=Invalid+email+or+password", status_code=302)
            except Exception as e:
                LOGGER.error(f"portal_login_submit: Cognito authentication error for {email}: {e}")
                return RedirectResponse(url="/portal/login?error=Authentication+service+error", status_code=302)
        else:
            LOGGER.warning("portal_login_submit: Cognito not configured - allowing login for registered customer %s WITHOUT password validation", email)

        LOGGER.debug(f"portal_login_submit: Setting session for authenticated user: {email}")
        request.session["user_email"] = email
        request.session["user_authenticated"] = True
        request.session["customer_id"] = customer.customer_id
        request.session["is_admin"] = customer.is_admin
        LOGGER.info(f"portal_login_submit: Login successful for customer {customer.customer_id} ({email})")
        return RedirectResponse(url="/portal/", status_code=302)

    @router.get("/portal/logout", response_class=RedirectResponse)
    async def portal_logout(request: Request):
        """Logout and redirect to login page."""
        request.session.clear()
        return RedirectResponse(url="/portal/login?success=You+have+been+logged+out", status_code=302)

    @router.get("/portal/forgot-password", response_class=HTMLResponse)
    async def portal_forgot_password(request: Request, error: Optional[str] = None, success: Optional[str] = None):
        """Forgot password page."""
        return deps.templates.TemplateResponse(
            request,
            "auth/forgot_password.html",
            _get_template_context(request, deps, error=error, success=success),
        )

    @router.post("/portal/forgot-password")
    async def portal_forgot_password_submit(request: Request, email: str = Form(...)):
        """Handle forgot password form submission."""
        if not deps.cognito_auth:
            return RedirectResponse(url="/portal/forgot-password?error=Password+reset+not+available", status_code=302)
        try:
            deps.cognito_auth.forgot_password(email)
            LOGGER.info(f"Password reset initiated for {email}")
            return RedirectResponse(url="/portal/reset-password?email=" + email, status_code=302)
        except ValueError as e:
            LOGGER.warning(f"Forgot password error for {email}: {e}")
            return RedirectResponse(url=f"/portal/forgot-password?error={str(e)}", status_code=302)
        except Exception as e:
            LOGGER.error(f"Forgot password error for {email}: {e}")
            return RedirectResponse(url="/portal/forgot-password?error=Password+reset+failed", status_code=302)

    @router.get("/portal/reset-password", response_class=HTMLResponse)
    async def portal_reset_password(request: Request, email: Optional[str] = None, error: Optional[str] = None, success: Optional[str] = None):
        """Reset password page."""
        return deps.templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            _get_template_context(request, deps, email=email, error=error, success=success),
        )

    @router.post("/portal/reset-password")
    async def portal_reset_password_submit(request: Request, email: str = Form(...), code: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
        """Handle reset password form submission."""
        if not deps.cognito_auth:
            return RedirectResponse(url="/portal/reset-password?error=Password+reset+not+available", status_code=302)
        if password != confirm_password:
            return RedirectResponse(url=f"/portal/reset-password?email={email}&error=Passwords+do+not+match", status_code=302)
        try:
            deps.cognito_auth.confirm_forgot_password(email, code, password)
            LOGGER.info(f"Password reset successful for {email}")
            return RedirectResponse(url="/portal/login?success=Password+reset+successful.+Please+log+in", status_code=302)
        except ValueError as e:
            LOGGER.warning(f"Reset password error for {email}: {e}")
            return RedirectResponse(url=f"/portal/reset-password?email={email}&error={str(e)}", status_code=302)
        except Exception as e:
            LOGGER.error(f"Reset password error for {email}: {e}")
            return RedirectResponse(url=f"/portal/reset-password?email={email}&error=Password+reset+failed", status_code=302)

    @router.get("/portal/change-password", response_class=HTMLResponse)
    async def portal_change_password(request: Request, reason: Optional[str] = None, error: Optional[str] = None, success: Optional[str] = None):
        """Change password page (for NEW_PASSWORD_REQUIRED challenge)."""
        if not request.session.get("challenge_session"):
            return RedirectResponse(url="/portal/login?error=Session+expired.+Please+log+in+again", status_code=302)
        email = request.session.get("challenge_email", "")
        return deps.templates.TemplateResponse(
            request,
            "auth/change_password.html",
            _get_template_context(request, deps, email=email, reason=reason, error=error, success=success),
        )

    @router.post("/portal/change-password")
    async def portal_change_password_submit(request: Request, new_password: str = Form(...), confirm_password: str = Form(...)):
        """Handle change password form submission (NEW_PASSWORD_REQUIRED challenge)."""
        if not deps.cognito_auth:
            return RedirectResponse(url="/portal/login?error=Authentication+not+available", status_code=302)
        session = request.session.get("challenge_session")
        email = request.session.get("challenge_email")
        if not session or not email:
            return RedirectResponse(url="/portal/login?error=Session+expired.+Please+log+in+again", status_code=302)
        if new_password != confirm_password:
            return RedirectResponse(url="/portal/change-password?error=Passwords+do+not+match", status_code=302)
        try:
            tokens = deps.cognito_auth.respond_to_new_password_challenge(email, new_password, session)
            request.session.pop("challenge_session", None)
            request.session.pop("challenge_email", None)
            customer = deps.customer_manager.get_customer_by_email(email) if deps.customer_manager else None
            if not customer:
                LOGGER.error(f"Customer not found for {email} after password change")
                return RedirectResponse(url="/portal/login?error=Account+not+found", status_code=302)
            request.session["access_token"] = tokens["access_token"]
            request.session["id_token"] = tokens["id_token"]
            request.session["user_email"] = email
            request.session["user_authenticated"] = True
            request.session["customer_id"] = customer.customer_id
            request.session["is_admin"] = customer.is_admin
            LOGGER.info(f"Password changed successfully for {email}, user logged in")
            return RedirectResponse(url="/portal/?success=Password+changed+successfully", status_code=302)
        except ValueError as e:
            LOGGER.warning(f"Password change error for {email}: {e}")
            return RedirectResponse(url=f"/portal/change-password?error={str(e)}", status_code=302)
        except Exception as e:
            LOGGER.error(f"Password change error for {email}: {e}")
            return RedirectResponse(url="/portal/change-password?error=Password+change+failed", status_code=302)

    @router.get("/portal/register", response_class=HTMLResponse)
    async def portal_register(request: Request, error: Optional[str] = None, success: Optional[str] = None):
        """Registration page."""
        return deps.templates.TemplateResponse(
            request,
            "auth/register.html",
            _get_template_context(request, deps, error=error, success=success),
        )

    @router.post("/portal/register", response_class=HTMLResponse)
    async def portal_register_submit(
        request: Request,
        customer_name: str = Form(...),
        email: str = Form(...),
        max_concurrent_worksets: int = Form(10),
        max_storage_gb: int = Form(500),
        billing_account_id: Optional[str] = Form(None),
        cost_center: Optional[str] = Form(None),
        s3_option: str = Form("auto"),
        custom_s3_bucket: Optional[str] = Form(None),
    ):
        """Handle registration form submission."""
        if not deps.customer_manager:
            return deps.templates.TemplateResponse(
                request, "auth/register.html",
                _get_template_context(request, deps, error="Customer management not configured"),
            )
        try:
            custom_bucket = None
            if s3_option == "byob" and custom_s3_bucket:
                custom_bucket = custom_s3_bucket.strip()
                if custom_bucket:
                    from daylib.s3_bucket_validator import S3BucketValidator
                    validator = S3BucketValidator(region=deps.region, profile=deps.profile)
                    result = validator.validate_bucket(custom_bucket)
                    if not result.is_valid:
                        error_msg = f"S3 bucket validation failed: {'; '.join(result.errors)}"
                        return deps.templates.TemplateResponse(
                            request, "auth/register.html",
                            _get_template_context(request, deps, error=error_msg),
                        )
            config = deps.customer_manager.onboard_customer(
                customer_name=customer_name,
                email=email,
                max_concurrent_worksets=max_concurrent_worksets,
                max_storage_gb=max_storage_gb,
                billing_account_id=billing_account_id,
                cost_center=cost_center,
                custom_s3_bucket=custom_bucket,
            )
            if deps.enable_auth and deps.cognito_auth:
                try:
                    LOGGER.info(f"Creating Cognito user for {email} (customer_id: {config.customer_id})")
                    deps.cognito_auth.create_customer_user(email=email, customer_id=config.customer_id, temporary_password=None)
                    LOGGER.info(f"Cognito user created successfully for {email}")
                except ValueError as e:
                    LOGGER.warning(f"Cognito user creation skipped: {e}")
                except Exception as e:
                    LOGGER.error(f"Failed to create Cognito user for {email}: {e}")
            bucket_info = f" Your S3 bucket: {config.s3_bucket}." if config.s3_bucket else ""
            if not deps.enable_auth:
                LOGGER.info(f"Auto-logging in new customer {config.customer_id} ({email}) in no-auth mode")
                request.session["user_email"] = email
                request.session["user_authenticated"] = True
                request.session["customer_id"] = config.customer_id
                request.session["is_admin"] = False
                success_msg = f"✅ Account created! Customer ID: {config.customer_id}.{bucket_info} Welcome!"
                return RedirectResponse(url=f"/portal/?success={success_msg}", status_code=302)
            else:
                success_msg = (
                    f"✅ Account created! Customer ID: {config.customer_id}.{bucket_info} "
                    f"📧 CHECK YOUR EMAIL (including spam folder) for your temporary password from no-reply@verificationemail.com. "
                    f"Use it to log in below."
                )
                return RedirectResponse(url=f"/portal/login?success={success_msg}", status_code=302)
        except Exception as e:
            LOGGER.error(f"Registration failed for {email}: {e}")
            return deps.templates.TemplateResponse(
                request, "auth/register.html",
                _get_template_context(request, deps, error=str(e)),
            )

    # ========== Worksets Routes ==========

    @router.get("/portal/worksets", response_class=HTMLResponse)
    async def portal_worksets(request: Request, page: int = 1):
        """Worksets list page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        worksets = []
        for ws_state in WorksetState:
            batch = deps.state_db.list_worksets_by_state(ws_state, limit=100)
            worksets.extend(batch)
        for ws in worksets:
            metadata = ws.get("metadata", {})
            if isinstance(metadata, dict):
                ws["sample_count"] = metadata.get("sample_count", 0)
                ws["pipeline_type"] = metadata.get("pipeline_type", "germline")
            else:
                ws["sample_count"] = 0
                ws["pipeline_type"] = "germline"
        per_page = 20
        total_pages = max(1, (len(worksets) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_worksets = worksets[start_idx:end_idx]
        return deps.templates.TemplateResponse(
            request,
            "worksets/list.html",
            _get_template_context(request, deps, customer=customer, worksets=paginated_worksets, page=page, total_pages=total_pages, active_page="worksets"),
        )

    @router.get("/portal/worksets/new", response_class=HTMLResponse)
    async def portal_worksets_new(request: Request):
        """New workset submission page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer, _ = _get_customer_for_session(request, deps)
        return deps.templates.TemplateResponse(
            request,
            "worksets/new.html",
            _get_template_context(request, deps, customer=customer, active_page="worksets"),
        )

    @router.get("/portal/worksets/archived", response_class=HTMLResponse)
    async def portal_worksets_archived(request: Request):
        """Archived worksets page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = None
        archived_worksets = []
        if deps.customer_manager:
            customers = deps.customer_manager.list_customers()
            if customers:
                customer = convert_customer_for_template(customers[0])
                all_archived = deps.state_db.list_archived_worksets(limit=500)
                customer_config = deps.customer_manager.get_customer_config(customers[0].customer_id)
                if customer_config:
                    archived_worksets = [w for w in all_archived if w.get("bucket") == customer_config.s3_bucket]
        return deps.templates.TemplateResponse(
            request,
            "worksets/archived.html",
            _get_template_context(request, deps, customer=customer, worksets=archived_worksets, active_page="worksets"),
        )

    @router.get("/portal/worksets/{workset_id}", response_class=HTMLResponse)
    async def portal_workset_detail(request: Request, workset_id: str):
        """Workset detail page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        workset = deps.state_db.get_workset(workset_id)
        if not workset:
            raise HTTPException(status_code=404, detail="Workset not found")
        customer = _get_first_customer_converted(deps)
        metadata = workset.get("metadata", {})
        if metadata:
            if "samples" in metadata and "samples" not in workset:
                workset["samples"] = metadata["samples"]
            for field in ["workset_name", "pipeline_type", "reference_genome", "notification_email", "enable_qc", "archive_results", "sample_count"]:
                if field in metadata and field not in workset:
                    workset[field] = metadata[field]
        return deps.templates.TemplateResponse(
            request,
            "worksets/detail.html",
            _get_template_context(request, deps, customer=customer, workset=workset, active_page="worksets"),
        )

    @router.get("/portal/worksets/{workset_id}/download")
    async def portal_workset_download(request: Request, workset_id: str):
        """Download workset results as a presigned URL redirect."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        workset = deps.state_db.get_workset(workset_id)
        if not workset:
            raise HTTPException(status_code=404, detail="Workset not found")
        if workset.get("state") != "complete":
            raise HTTPException(status_code=400, detail=f"Workset is not complete (current state: {workset.get('state')})")
        bucket = workset.get("bucket")
        prefix = workset.get("prefix", "").rstrip("/")
        results_prefix = f"{prefix}/results/" if prefix else "results/"
        try:
            session_kwargs = {"region_name": deps.region}
            if deps.profile:
                session_kwargs["profile_name"] = deps.profile
            session = boto3.Session(**session_kwargs)
            s3 = session.client("s3")
            response = s3.list_objects_v2(Bucket=bucket, Prefix=results_prefix, MaxKeys=100)
            result_files = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1]
                if filename and not filename.startswith("."):
                    result_files.append({"key": key, "filename": filename, "size": obj.get("Size", 0)})
            if not result_files:
                raise HTTPException(status_code=404, detail="No result files found for this workset")
            main_results = [f for f in result_files if f["filename"].endswith((".vcf", ".vcf.gz", ".bam", ".cram", ".html"))]
            download_file = main_results[0] if main_results else result_files[0]
            presigned_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": download_file["key"], "ResponseContentDisposition": f'attachment; filename="{download_file["filename"]}"'},
                ExpiresIn=3600,
            )
            return RedirectResponse(url=presigned_url, status_code=302)
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.error(f"Error generating download for workset {workset_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate download: {str(e)}")

    # ========== Manifest Generator Routes ==========

    @router.get("/portal/yaml-generator", response_class=HTMLResponse)
    async def portal_yaml_generator(request: Request):
        """Redirect to manifest-generator."""
        return RedirectResponse(url="/portal/manifest-generator", status_code=302)

    @router.get("/portal/manifest-generator", response_class=HTMLResponse)
    async def portal_manifest_generator(request: Request):
        """Manifest/YAML generator page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        return deps.templates.TemplateResponse(
            request,
            "manifest_generator.html",
            _get_template_context(request, deps, customer=customer, active_page="manifest"),
        )

    # ========== Files Routes ==========

    @router.get("/portal/files", response_class=HTMLResponse)
    async def portal_files(request: Request, prefix: str = "", subject_id: str = "", biosample_id: str = ""):
        """File registry page - main file management interface."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        files = []
        stats = {"total_files": 0, "total_size": 0, "unique_subjects": 0, "unique_biosamples": 0}
        buckets = []
        if deps.file_registry and customer:
            customer_id = customer.customer_id
            try:
                if subject_id:
                    files = deps.file_registry.search_files_by_tag(customer_id, f"subject:{subject_id}")
                elif biosample_id:
                    files = deps.file_registry.search_files_by_tag(customer_id, f"biosample:{biosample_id}")
                else:
                    file_registrations = deps.file_registry.list_customer_files(customer_id, limit=100)
                    files = [
                        {"file_id": f.file_id, "customer_id": f.customer_id, "s3_bucket": f.s3_bucket, "s3_key": f.s3_key,
                         "filename": f.s3_key.split("/")[-1] if f.s3_key else "", "size": f.file_metadata.file_size_bytes if f.file_metadata else 0,
                         "size_formatted": format_file_size(f.file_metadata.file_size_bytes) if f.file_metadata else "0 B",
                         "file_type": f.file_metadata.file_format if f.file_metadata else "unknown",
                         "subject_id": f.biosample_metadata.subject_id if f.biosample_metadata else None,
                         "biosample_id": f.biosample_metadata.biosample_id if f.biosample_metadata else None,
                         "registered_at": f.registered_at.isoformat() if f.registered_at else None}
                        for f in file_registrations
                    ]
                stats["total_files"] = len(files)
                stats["total_size"] = sum(f.get("size", 0) for f in files)
                stats["unique_subjects"] = len(set(f.get("subject_id") for f in files if f.get("subject_id")))
                stats["unique_biosamples"] = len(set(f.get("biosample_id") for f in files if f.get("biosample_id")))
            except Exception as e:
                LOGGER.warning(f"Failed to load files: {e}")
        if deps.linked_bucket_manager and customer:
            try:
                linked_buckets = deps.linked_bucket_manager.list_customer_buckets(customer.customer_id)
                buckets = [{"bucket_id": b.bucket_id, "bucket_name": b.bucket_name, "display_name": b.display_name} for b in linked_buckets]
            except Exception as e:
                LOGGER.warning(f"Failed to load buckets: {e}")
        return deps.templates.TemplateResponse(
            request,
            "files/index.html",
            _get_template_context(request, deps, customer=customer, files=files, stats=stats, buckets=buckets, prefix=prefix, subject_id=subject_id, biosample_id=biosample_id, active_page="files"),
        )

    @router.get("/portal/files/buckets", response_class=HTMLResponse)
    async def portal_files_buckets(request: Request):
        """Linked buckets management page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        buckets = []
        if deps.linked_bucket_manager and customer:
            try:
                linked_buckets = deps.linked_bucket_manager.list_customer_buckets(customer.customer_id)
                buckets = [
                    {"bucket_id": b.bucket_id, "bucket_name": b.bucket_name, "bucket_type": b.bucket_type, "display_name": b.display_name,
                     "description": b.description, "is_validated": b.is_validated, "can_read": b.can_read, "can_write": b.can_write,
                     "can_list": b.can_list, "read_only": b.read_only, "linked_at": b.linked_at.isoformat() if b.linked_at else None}
                    for b in linked_buckets
                ]
            except Exception as e:
                LOGGER.warning(f"Failed to load buckets: {e}")
        return deps.templates.TemplateResponse(
            request,
            "files/buckets.html",
            _get_template_context(request, deps, customer=customer, buckets=buckets, active_page="files"),
        )

    @router.get("/portal/files/browse/{bucket_id}", response_class=HTMLResponse)
    async def portal_files_browse(request: Request, bucket_id: str, prefix: str = ""):
        """Browse files in a linked bucket."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer, _ = _get_customer_for_session(request, deps)
        if not customer:
            if deps.settings.demo_mode and deps.customer_manager:
                customers = deps.customer_manager.list_customers()
                if customers:
                    customer = convert_customer_for_template(customers[0])
        if not customer:
            return RedirectResponse(url="/portal/login?error=No+customer+account+found", status_code=302)
        bucket = None
        items = []
        breadcrumbs = []
        current_prefix = prefix.rstrip("/") + "/" if prefix else ""
        parent_prefix = "/".join(current_prefix.rstrip("/").split("/")[:-1])
        if parent_prefix:
            parent_prefix += "/"
        if deps.linked_bucket_manager:
            bucket_obj = deps.linked_bucket_manager.get_bucket(bucket_id)
            if bucket_obj:
                if bucket_obj.customer_id != customer.customer_id:
                    return RedirectResponse(url="/portal/files/buckets?error=Access+denied+to+this+bucket", status_code=302)
                bucket = {"bucket_id": bucket_obj.bucket_id, "bucket_name": bucket_obj.bucket_name, "display_name": bucket_obj.display_name}
                try:
                    session_kwargs = {"region_name": deps.region}
                    if deps.profile:
                        session_kwargs["profile_name"] = deps.profile
                    session = boto3.Session(**session_kwargs)
                    s3 = session.client("s3")
                    response = s3.list_objects_v2(Bucket=bucket_obj.bucket_name, Prefix=current_prefix, Delimiter="/", MaxKeys=500)
                    for cp in response.get("CommonPrefixes", []):
                        folder_path = cp["Prefix"]
                        folder_name = folder_path.rstrip("/").split("/")[-1]
                        items.append({"name": folder_name, "type": "folder", "prefix": folder_path, "icon": "folder"})
                    for obj in response.get("Contents", []):
                        if obj["Key"] == current_prefix:
                            continue
                        filename = obj["Key"].split("/")[-1]
                        if filename:
                            items.append({"name": filename, "type": "file", "key": obj["Key"], "size": obj.get("Size", 0),
                                          "size_formatted": format_file_size(obj.get("Size", 0)), "icon": get_file_icon(filename),
                                          "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None})
                except Exception as e:
                    LOGGER.warning(f"Failed to browse bucket {bucket_id}: {e}")
        if current_prefix:
            parts = current_prefix.rstrip("/").split("/")
            for i, part in enumerate(parts):
                breadcrumbs.append({"name": part, "prefix": "/".join(parts[: i + 1]) + "/"})
        return deps.templates.TemplateResponse(
            request,
            "files/browse.html",
            _get_template_context(request, deps, customer=customer, bucket=bucket, items=items, breadcrumbs=breadcrumbs,
                                  current_prefix=current_prefix, parent_prefix=parent_prefix, active_page="files"),
        )

    @router.get("/portal/files/register", response_class=HTMLResponse)
    async def portal_files_register(request: Request):
        """File registration page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer, _ = _get_customer_for_session(request, deps)
        buckets = []
        if deps.linked_bucket_manager and customer:
            try:
                linked_buckets = deps.linked_bucket_manager.list_customer_buckets(customer.customer_id)
                buckets = [{"bucket_id": b.bucket_id, "bucket_name": b.bucket_name, "display_name": b.display_name,
                            "is_validated": b.is_validated, "can_read": b.can_read, "can_write": b.can_write, "can_list": b.can_list}
                           for b in linked_buckets]
            except Exception as e:
                LOGGER.warning(f"Failed to load buckets: {e}")
        return deps.templates.TemplateResponse(
            request,
            "files/register.html",
            _get_template_context(request, deps, customer=customer, buckets=buckets, active_page="files"),
        )

    @router.post("/portal/files/register", response_model=PortalFileAutoRegisterResponse)
    async def portal_files_register_submit(request: Request, payload: PortalFileAutoRegisterRequest):
        """Register selected discovered files from a linked bucket."""
        user_email = request.session.get("user_email")
        LOGGER.debug(f"portal_files_register_submit: Session user_email: '{user_email}'")
        if not user_email:
            raise HTTPException(status_code=401, detail="Not authenticated")
        customer, customer_config = _get_customer_for_session(request, deps)
        if not customer:
            raise HTTPException(status_code=401, detail="No customer account found")
        customer_id = customer.customer_id
        if not deps.file_registry or not deps.linked_bucket_manager:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="File management not configured")
        bucket_name = None
        if payload.bucket_id:
            bucket_obj = deps.linked_bucket_manager.get_bucket(payload.bucket_id)
            if not bucket_obj:
                raise HTTPException(status_code=404, detail=f"Bucket ID {payload.bucket_id} not found")
            if bucket_obj.customer_id != customer_id:
                raise HTTPException(status_code=403, detail="Access denied to this bucket")
            bucket_name = bucket_obj.bucket_name
        elif payload.bucket_name:
            bucket_name = payload.bucket_name
        else:
            raise HTTPException(status_code=400, detail="bucket_id or bucket_name required")
        # Implementation would continue here - this is a stub for the route extraction
        return PortalFileAutoRegisterResponse(registered_count=0, skipped_count=0, errors=["Route stub - full implementation in workset_api.py"])

    @router.get("/portal/files/upload", response_class=HTMLResponse)
    async def portal_files_upload(request: Request):
        """File upload page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        buckets = []
        if deps.linked_bucket_manager and customer:
            try:
                linked_buckets = deps.linked_bucket_manager.list_customer_buckets(customer.customer_id)
                buckets = [{"bucket_id": b.bucket_id, "bucket_name": b.bucket_name, "display_name": b.display_name,
                            "is_validated": b.is_validated, "can_read": b.can_read, "can_write": b.can_write}
                           for b in linked_buckets]
            except Exception as e:
                LOGGER.warning(f"Failed to load buckets: {e}")
        return deps.templates.TemplateResponse(
            request,
            "files/upload.html",
            _get_template_context(request, deps, customer=customer, buckets=buckets, active_page="files"),
        )

    @router.post("/portal/files/upload")
    async def portal_files_upload_submit(request: Request, bucket_id: str = Form(...), prefix: str = Form(""), file: UploadFile = File(...)):
        """Handle file upload to S3 bucket."""
        user_email = request.session.get("user_email")
        customer_id = request.session.get("customer_id")
        if not user_email or not customer_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if not deps.linked_bucket_manager:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="File management not configured")
        LOGGER.info(f"Upload request from {user_email}: {file.filename} to bucket {bucket_id}")
        bucket_obj = deps.linked_bucket_manager.get_bucket(bucket_id)
        if not bucket_obj:
            raise HTTPException(status_code=404, detail="Bucket not found")
        if bucket_obj.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied to this bucket")
        if not bucket_obj.can_write:
            raise HTTPException(status_code=403, detail="Write access not enabled for this bucket")
        try:
            session_kwargs = {"region_name": deps.region}
            if deps.profile:
                session_kwargs["profile_name"] = deps.profile
            session = boto3.Session(**session_kwargs)
            s3 = session.client("s3")
            s3_key = f"{prefix.strip('/')}/{file.filename}" if prefix else file.filename
            s3.upload_fileobj(file.file, bucket_obj.bucket_name, s3_key)
            LOGGER.info(f"Uploaded {file.filename} to s3://{bucket_obj.bucket_name}/{s3_key}")
            return {"success": True, "bucket": bucket_obj.bucket_name, "key": s3_key, "filename": file.filename}
        except Exception as e:
            LOGGER.error(f"Upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    @router.get("/portal/files/filesets", response_class=HTMLResponse)
    async def portal_files_filesets(request: Request):
        """File sets management page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        filesets = []
        if deps.file_registry and customer:
            try:
                fileset_objs = deps.file_registry.list_customer_filesets(customer.customer_id)
                filesets = [
                    {"fileset_id": fs.fileset_id, "customer_id": fs.customer_id, "name": fs.name, "description": fs.description,
                     "file_count": len(fs.file_ids), "created_at": fs.created_at.isoformat() if fs.created_at else None}
                    for fs in fileset_objs
                ]
            except Exception as e:
                LOGGER.warning(f"Failed to load filesets: {e}")
        return deps.templates.TemplateResponse(
            request,
            "files/filesets.html",
            _get_template_context(request, deps, customer=customer, filesets=filesets, active_page="files"),
        )

    @router.get("/portal/files/filesets/{fileset_id}", response_class=HTMLResponse)
    async def portal_files_fileset_detail(request: Request, fileset_id: str):
        """File set detail page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        fileset = None
        files = []
        if deps.file_registry:
            try:
                fileset = deps.file_registry.get_fileset(fileset_id)
                if fileset:
                    files = deps.file_registry.get_fileset_files(fileset_id)
            except Exception as e:
                LOGGER.warning(f"Failed to load fileset: {e}")
        if not fileset:
            raise HTTPException(status_code=404, detail="File set not found")
        unique_subjects = len(set(f.biosample_metadata.subject_id for f in files if f.biosample_metadata and f.biosample_metadata.subject_id))
        return deps.templates.TemplateResponse(
            request,
            "files/fileset_detail.html",
            _get_template_context(request, deps, customer=customer, fileset=fileset, files=files, unique_subjects=unique_subjects, active_page="files"),
        )

    @router.get("/portal/files/{file_id}", response_class=HTMLResponse)
    async def portal_files_detail(request: Request, file_id: str):
        """File detail page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        file = None
        workset_history = []
        if deps.file_registry:
            try:
                file = deps.file_registry.get_file(file_id)
                if file:
                    workset_history = deps.file_registry.get_file_workset_history(file_id)
            except Exception as e:
                LOGGER.warning(f"Failed to load file: {e}")
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        return deps.templates.TemplateResponse(
            request,
            "files/detail.html",
            _get_template_context(request, deps, customer=customer, file=file, workset_history=workset_history, active_page="files"),
        )

    @router.get("/portal/files/{file_id}/edit", response_class=HTMLResponse)
    async def portal_files_edit(request: Request, file_id: str):
        """File edit page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        file = None
        if deps.file_registry:
            try:
                file = deps.file_registry.get_file(file_id)
            except Exception as e:
                LOGGER.warning(f"Failed to load file for edit: {e}")
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        return deps.templates.TemplateResponse(
            request,
            "files/edit_file.html",
            _get_template_context(request, deps, customer=customer, file=file, active_page="files"),
        )

    @router.get("/portal/files/browser", response_class=HTMLResponse)
    async def portal_files_browser(request: Request, prefix: str = ""):
        """S3 file browser (legacy, uses customer's primary bucket)."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = None
        folders: List[Dict[str, Any]] = []
        files: List[Dict[str, Any]] = []
        storage: Dict[str, Any] = {"used_gb": 0, "max_gb": 500, "files": files, "folders": folders}
        if deps.customer_manager:
            customers = deps.customer_manager.list_customers()
            if customers:
                customer_raw = customers[0]
                customer = convert_customer_for_template(customer_raw)
                storage["max_gb"] = customer.max_storage_gb
                try:
                    session_kwargs = {"region_name": deps.region}
                    if deps.profile:
                        session_kwargs["profile_name"] = deps.profile
                    session = boto3.Session(**session_kwargs)
                    s3 = session.client("s3")
                    response = s3.list_objects_v2(Bucket=customer.s3_bucket, Prefix=prefix, Delimiter="/")
                    for cp in response.get("CommonPrefixes", []):
                        folder_path = cp["Prefix"]
                        folder_name = folder_path.rstrip("/").split("/")[-1]
                        folders.append({"name": folder_name, "path": folder_path})
                    for obj in response.get("Contents", []):
                        if obj["Key"] == prefix:
                            continue
                        filename = obj["Key"].split("/")[-1]
                        if filename:
                            files.append({"name": filename, "key": obj["Key"], "size": obj.get("Size", 0),
                                          "size_formatted": format_file_size(obj.get("Size", 0)),
                                          "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None})
                except Exception as e:
                    LOGGER.warning(f"Failed to browse S3: {e}")
        return deps.templates.TemplateResponse(
            request,
            "files/browser.html",
            _get_template_context(request, deps, customer=customer, storage=storage, prefix=prefix, active_page="files"),
        )

    # ========== Usage Routes ==========

    @router.get("/portal/usage", response_class=HTMLResponse)
    async def portal_usage(request: Request):
        """Usage and billing page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = None
        usage = {"total_cost": 0, "cost_change": 0, "vcpu_hours": 0, "memory_gb_hours": 0, "storage_gb": 0, "active_worksets": 0}
        usage_details: List[Dict[str, Any]] = []
        if deps.customer_manager:
            customers = deps.customer_manager.list_customers()
            if customers:
                customer = convert_customer_for_template(customers[0])
                customer_usage = deps.customer_manager.get_customer_usage(customers[0].customer_id)
                if customer_usage:
                    usage.update(customer_usage)
        return deps.templates.TemplateResponse(
            request,
            "usage.html",
            _get_template_context(request, deps, customer=customer, usage=usage, usage_details=usage_details, active_page="usage"),
        )

    # ========== Biospecimen Routes ==========

    @router.get("/portal/biospecimen", response_class=HTMLResponse)
    @router.get("/portal/biospecimen/subjects", response_class=HTMLResponse)
    async def portal_biospecimen_subjects(request: Request):
        """Subjects management page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer_id = request.session.get("customer_id", "default-customer")
        customer = _get_first_customer_converted(deps)
        subjects: List[Dict[str, Any]] = []
        stats = {"subjects": 0, "biosamples": 0, "libraries": 0}
        # Biospecimen registry would be loaded here if available
        return deps.templates.TemplateResponse(
            request,
            "biospecimen/subjects.html",
            _get_template_context(request, deps, customer=customer, subjects=subjects, stats=stats, active_page="biospecimen"),
        )

    # ========== Account Routes ==========

    @router.get("/portal/account", response_class=HTMLResponse)
    async def portal_account(request: Request):
        """Account settings page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        app_settings = deps.settings
        env_vars = {
            "AWS_PROFILE": app_settings.aws_profile,
            "AWS_DEFAULT_REGION": app_settings.aws_default_region,
            "AWS_REGION": app_settings.get_effective_region(),
            "AWS_ACCESS_KEY_ID": "***" if os.getenv("AWS_ACCESS_KEY_ID") else None,
            "AWS_SECRET_ACCESS_KEY": "***" if os.getenv("AWS_SECRET_ACCESS_KEY") else None,
            "AWS_ACCOUNT_ID": app_settings.aws_account_id,
            "DAYLILY_CONTROL_BUCKET": app_settings.daylily_control_bucket,
            "DAYLILY_MONITOR_BUCKET": app_settings.daylily_monitor_bucket,
            "WORKSET_TABLE_NAME": app_settings.workset_table_name,
            "CUSTOMER_TABLE_NAME": app_settings.customer_table_name,
            "COGNITO_USER_POOL_ID": app_settings.cognito_user_pool_id,
            "COGNITO_APP_CLIENT_ID": app_settings.cognito_app_client_id,
            "DAYLILY_PRIMARY_REGION": os.getenv("DAYLILY_PRIMARY_REGION"),
            "DAYLILY_MULTI_REGION": os.getenv("DAYLILY_MULTI_REGION"),
            "APPTAINER_HOME": os.getenv("APPTAINER_HOME"),
            "DAY_BIOME": os.getenv("DAY_BIOME"),
            "DAY_ROOT": os.getenv("DAY_ROOT"),
        }
        return deps.templates.TemplateResponse(
            request,
            "account.html",
            _get_template_context(request, deps, customer=customer, active_page="account", env_vars=env_vars),
        )

    # ========== Static Pages ==========

    @router.get("/portal/docs", response_class=HTMLResponse)
    async def portal_docs(request: Request):
        """Documentation page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        return deps.templates.TemplateResponse(
            request,
            "docs.html",
            _get_template_context(request, deps, customer=customer, active_page="docs"),
        )

    @router.get("/portal/support", response_class=HTMLResponse)
    async def portal_support(request: Request):
        """Support/Contact page."""
        auth_redirect = _require_portal_auth(request)
        if auth_redirect:
            return auth_redirect
        customer = _get_first_customer_converted(deps)
        return deps.templates.TemplateResponse(
            request,
            "support.html",
            _get_template_context(request, deps, customer=customer, active_page="support"),
        )

    return router

