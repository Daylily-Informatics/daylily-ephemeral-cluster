# Password Reset & No-Auth Mode Fixes

## Issues Fixed

### 1. Password Reset Not Available ✅
**Problem**: `/portal/forgot-password` returned 404 - no password reset functionality existed.

**Solution**: Implemented complete password reset flow using AWS Cognito.

### 2. No-Auth Mode Broken ✅
**Problem**: When running with `enable_auth=False`, the portal still required login and failed with customer info errors.

**Solution**: Modified authentication logic to automatically create a session with a default customer when auth is disabled.

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

## Testing Instructions

### Test Password Reset (Auth Mode)

1. **Start server with auth:**
   ```bash
   ./examples/run_api_with_new_cognito.sh
   ```

2. **Test forgot password:**
   - Go to http://localhost:8000/portal/login
   - Click "Forgot password?"
   - Enter: `john@dyly.bio`
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
   - Go to http://localhost:8000/portal
   - Should automatically log you in
   - Should see dashboard with customer data

3. **Test registration:**
   - Go to http://localhost:8000/portal/register
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

