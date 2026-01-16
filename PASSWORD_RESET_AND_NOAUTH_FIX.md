# Password Reset & No-Auth Mode Fixes

## Issues Fixed

### 1. Password Reset Not Available ✅
**Problem**: `/portal/forgot-password` returned 404 - no password reset functionality existed.

**Solution**: Implemented complete password reset flow using AWS Cognito.

### 2. No-Auth Mode Broken ✅
**Problem**: When running with `enable_auth=False`, the portal still required login and failed with customer info errors.

**Solution**: Modified authentication logic to automatically create a session with a default customer when auth is disabled.

### 3. Registration Not Creating Cognito Users ✅
**Problem**: Registration UI created DynamoDB customer records but not Cognito users, causing "User does not exist" errors on login.

**Solution**: Modified registration endpoint to create both DynamoDB customer record AND Cognito user when auth is enabled.

---

## Password Reset Implementation

### Backend Changes

#### `daylib/workset_auth.py`
Added two new methods to `CognitoAuth` class:

```python
def forgot_password(email: str) -> None:
    """Initiate password reset - sends verification code to email"""
    
def confirm_forgot_password(email: str, confirmation_code: str, new_password: str) -> None:
    """Complete password reset with verification code"""
```

#### `daylib/workset_api.py`
Added four new endpoints:

1. **GET `/portal/forgot-password`** - Display forgot password form
2. **POST `/portal/forgot-password`** - Send verification code to email
3. **GET `/portal/reset-password`** - Display reset password form
4. **POST `/portal/reset-password`** - Confirm code and set new password

### Frontend Changes

#### `templates/auth/forgot_password.html`
- Clean, user-friendly form to enter email
- Sends verification code via Cognito
- Matches existing portal design

#### `templates/auth/reset_password.html`
- Form to enter verification code and new password
- Password confirmation validation
- Password requirements displayed
- Toggle password visibility

### Password Reset Flow

```
1. User clicks "Forgot password?" on login page
   ↓
2. User enters email → POST /portal/forgot-password
   ↓
3. Cognito sends 6-digit code to email
   ↓
4. User redirected to /portal/reset-password
   ↓
5. User enters code + new password → POST /portal/reset-password
   ↓
6. Cognito validates code and updates password
   ↓
7. User redirected to login with success message
```

### Security Features

- ✅ No user enumeration (same response for valid/invalid emails)
- ✅ Verification code expires after 1 hour
- ✅ Password requirements enforced (8+ chars, upper, lower, number, symbol)
- ✅ Rate limiting via Cognito
- ✅ All errors logged for security monitoring

---

## No-Auth Mode Fix

### Problem Details

When running `python examples/run_api_without_auth.py`:
1. Portal showed "Continue to Dashboard" button
2. Clicking it redirected to login page
3. Even after registration, couldn't access dashboard
4. Customer info was null, causing errors

### Solution

Modified `require_portal_auth()` function in `daylib/workset_api.py`:

```python
def require_portal_auth(request: Request) -> Optional[RedirectResponse]:
    """Check authentication - handles both auth and no-auth modes."""
    
    if not enable_auth:
        # No-auth mode: Auto-create session
        if not request.session.get("user_email"):
            # Try to use first customer from database
            customers = customer_manager.list_customers()
            if customers:
                default_customer = customers[0]
                # Set session with real customer data
            else:
                # No customers - create demo session
                request.session["user_email"] = "demo@daylily.local"
                request.session["customer_id"] = "demo-customer"
                request.session["is_admin"] = True
        
        return None  # Allow access
    
    # Auth enabled - require valid login
    if not request.session.get("user_email"):
        return RedirectResponse(url="/portal/login")
    
    return None
```

### Behavior

**With Customers in Database:**
- Uses first customer automatically
- Logs: `"No-auth mode: Using first customer {id} ({email})"`
- Full customer data available (storage limits, etc.)

**Without Customers:**
- Creates demo session
- Logs: `"No-auth mode: No customers found, creating demo session"`
- Demo customer has admin privileges

---

## Registration Fix

### Problem Details

When a user registered via `/portal/register`:
1. ✅ DynamoDB customer record was created
2. ❌ Cognito user was NOT created
3. ❌ Login failed with "User does not exist"

### Solution

Modified `portal_register_submit()` in `daylib/workset_api.py`:

```python
# After creating customer in DynamoDB
config = customer_manager.onboard_customer(...)

# Now also create Cognito user if auth is enabled
if enable_auth and cognito_auth:
    cognito_auth.create_customer_user(
        email=email,
        customer_id=config.customer_id,
        temporary_password=None,  # Cognito generates and emails it
    )
```

### Behavior

**With Auth Enabled:**
- Creates DynamoDB customer record
- Creates Cognito user with temporary password
- Cognito emails temporary password to user
- User must change password on first login (Cognito default)
- Success message: "Check your email for login credentials"

**Without Auth:**
- Only creates DynamoDB customer record
- No Cognito user needed
- Success message: "Please log in"

**Error Handling:**
- If Cognito user already exists: Log warning, continue
- If Cognito creation fails: Log error, continue (customer record still created)
- Registration never fails due to Cognito errors

---

## Testing Instructions

### Test Registration (Auth Mode)

1. **Start server with auth:**
   ```bash
   ./examples/run_api_with_new_cognito.sh
   ```

2. **Test registration:**
   - Go to http://localhost:8001/portal/register
   - Fill in form (use a real email you can access)
   - Submit
   - Should see: "Check your email for login credentials"

3. **Check email:**
   - You should receive email from Cognito with temporary password
   - Subject: "Your temporary password"

4. **Test first login:**
   - Go to http://localhost:8001/portal/login
   - Enter email and temporary password
   - Cognito will require password change
   - Set new password
   - Should log in successfully!

5. **Verify with AWS CLI:**
   ```bash
   aws cognito-idp admin-get-user \
     --user-pool-id $COGNITO_USER_POOL_ID \
     --username your-email@example.com \
     --region us-west-2
   ```

### Test Password Reset (Auth Mode)

1. **Start server with auth:**
   ```bash
   ./examples/run_api_with_new_cognito.sh
   ```

2. **Test forgot password:**
   - Go to http://localhost:8001/portal/login
   - Click "Forgot password?"
   - Enter your email
   - Check email for 6-digit code

3. **Test reset password:**
   - Enter the 6-digit code
   - Enter new password (must meet requirements)
   - Confirm password
   - Should redirect to login with success message

4. **Test login with new password:**
   - Login with new password
   - Should work!

### Test No-Auth Mode

1. **Start server without auth:**
   ```bash
   python examples/run_api_without_auth.py
   ```

2. **Test direct access:**
   - Go to http://localhost:8001/portal
   - Should automatically log you in
   - Should see dashboard with customer data

3. **Test registration:**
   - Go to http://localhost:8001/portal/register
   - Create a new customer
   - Should work and redirect to dashboard

4. **Check logs:**
   - Should see: `"No-auth mode: Using first customer..."`
   - Or: `"No-auth mode: No customers found, creating demo session"`

---

## Files Modified

- `daylib/workset_auth.py` - Added password reset methods
- `daylib/workset_api.py` - Added endpoints + fixed no-auth mode
- `templates/auth/forgot_password.html` - New
- `templates/auth/reset_password.html` - New

## Commits

- `0d16c82d` - Add password reset functionality and fix no-auth mode
- `6bd3cb8c` - Fix registration to create Cognito user

## Summary

All three issues are now fixed:

1. ✅ **Password reset works** - Full forgot/reset password flow with Cognito
2. ✅ **No-auth mode works** - Portal accessible without login when auth disabled
3. ✅ **Registration creates Cognito users** - Users can actually log in after registering

The registration flow now properly creates both:
- DynamoDB customer record (for billing, limits, etc.)
- Cognito user (for authentication)

Users receive a temporary password via email and must change it on first login.

