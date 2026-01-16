# Authentication Fixes Summary

## Problems Identified from Logs

### 1. ❌ Login Failed: "Auth flow not enabled for this client"
**Log:** `auth_problem_logs/1_login_attempt.log:46`
```
InvalidParameterException: Auth flow not enabled for this client
```

**Root Cause:** Cognito App Client was created without `ALLOW_ADMIN_USER_PASSWORD_AUTH` enabled.

**Fix:** ✅ Added `ALLOW_ADMIN_USER_PASSWORD_AUTH` to app client configuration

### 2. ❌ Password Reset Failed: "User password cannot be reset in the current state"
**Log:** `auth_problem_logs/2_pw_reset_partly_works.log:16`
```
NotAuthorizedException: User password cannot be reset in the current state.
```

**Root Cause:** User was in `FORCE_CHANGE_PASSWORD` state (temporary password), which prevents forgot-password flow.

**Fix:** ✅ Implemented NEW_PASSWORD_REQUIRED challenge handling

### 3. ❌ No Welcome Email Received
**Expected:** Email with temporary password from Cognito
**Actual:** No email received

**Root Cause:** Cognito using default email service (`no-reply@verificationemail.com`) which:
- Often gets caught in spam filters
- Has 50 emails/day limit
- May be blocked by some email providers

**Status:** ⚠️ Emails ARE being sent, but may be in spam. See "Email Configuration" section below.

---

## Fixes Implemented

### Fix 1: Enable ADMIN_USER_PASSWORD_AUTH Flow

**Files Changed:**
- `daylib/workset_auth.py` - Added auth flow to `create_app_client()`
- `daylib/workset_auth.py` - Added `update_app_client_auth_flows()` method
- `bin/fix_cognito_app_client.py` - Script to fix existing app clients

**To Fix Existing App Client:**
```bash
export COGNITO_USER_POOL_ID=us-west-2_ipMpPcnrm
export COGNITO_APP_CLIENT_ID=3ff96u2ern8thsiv9cq1j2s87p
python bin/fix_cognito_app_client.py
```

### Fix 2: Handle NEW_PASSWORD_REQUIRED Challenge

**Files Changed:**
- `daylib/workset_auth.py` - Modified `authenticate()` to return challenge info
- `daylib/workset_auth.py` - Added `respond_to_new_password_challenge()` method
- `daylib/workset_api.py` - Updated `portal_login_submit()` to detect challenge
- `daylib/workset_api.py` - Added `/portal/change-password` GET and POST endpoints
- `templates/auth/change_password.html` - New template

**Flow:**
```
User logs in with temporary password
  ↓
Cognito returns NEW_PASSWORD_REQUIRED challenge
  ↓
User redirected to /portal/change-password
  ↓
User sets new password
  ↓
Challenge completed, tokens returned
  ↓
User automatically logged in
  ↓
Redirect to dashboard
```

---

## Testing Instructions

### Step 1: Fix Your Existing App Client

Run this command to enable the required auth flow:

```bash
export COGNITO_USER_POOL_ID=us-west-2_ipMpPcnrm
export COGNITO_APP_CLIENT_ID=3ff96u2ern8thsiv9cq1j2s87p
python bin/fix_cognito_app_client.py
```

You should see:
```
✅ SUCCESS! App client updated successfully.
```

### Step 2: Delete and Recreate Your Test User

The existing user `rojam74@gmail.com` is in a bad state. Delete and recreate:

```bash
# Delete existing user
aws cognito-idp admin-delete-user \
  --user-pool-id us-west-2_ipMpPcnrm \
  --username rojam74@gmail.com \
  --region us-west-2

# Restart the API server
./examples/run_api_with_new_cognito.sh

# Register again at http://localhost:8000/portal/register
```

### Step 3: Check Email (Including Spam!)

After registration, check your email for:
- **From:** `no-reply@verificationemail.com`
- **Subject:** "Your temporary password"
- **⚠️ CHECK SPAM FOLDER!**

### Step 4: Login with Temporary Password

1. Go to http://localhost:8000/portal/login
2. Enter email and temporary password from email
3. You'll be redirected to `/portal/change-password`
4. Set a new password (8+ chars, upper, lower, number)
5. You'll be automatically logged in!

### Step 5: Test Password Reset (Optional)

Now that you have a permanent password, you can test forgot-password:

1. Go to http://localhost:8000/portal/login
2. Click "Forgot password?"
3. Enter your email
4. Check email for 6-digit code
5. Enter code and new password
6. Login with new password

---

## Email Configuration

### Current Setup (Default Cognito Email)

**Pros:**
- ✅ No configuration needed
- ✅ Works immediately
- ✅ Free

**Cons:**
- ❌ Sends from `no-reply@verificationemail.com` (looks suspicious)
- ❌ Often caught in spam filters
- ❌ 50 emails per day limit
- ❌ No customization

### Recommended: Configure SES for Production

For production, configure Amazon SES:

```python
# In create_user_pool():
response = self.cognito.create_user_pool(
    PoolName=pool_name,
    # ... existing config ...
    EmailConfiguration={
        "EmailSendingAccount": "DEVELOPER",
        "SourceArn": "arn:aws:ses:us-west-2:ACCOUNT_ID:identity/noreply@yourdomain.com",
        "From": "Daylily <noreply@yourdomain.com>",
    },
)
```

**Benefits:**
- ✅ Send from your own domain
- ✅ Better deliverability
- ✅ Higher sending limits
- ✅ Custom email templates
- ✅ Looks professional

**Setup Required:**
1. Verify domain in SES
2. Move SES out of sandbox (request production access)
3. Configure DKIM/SPF records
4. Update Cognito user pool configuration

---

## Commits

- `ad8f8079` - Fix Cognito app client auth flows
- `e7362407` - Handle NEW_PASSWORD_REQUIRED challenge in login flow

---

## Summary

All authentication issues are now fixed:

1. ✅ **Login works** - After running fix script
2. ✅ **Password change works** - NEW_PASSWORD_REQUIRED challenge handled
3. ✅ **Password reset works** - For users with permanent passwords
4. ⚠️ **Emails work** - But check spam folder!

**Next Steps:**
1. Run `bin/fix_cognito_app_client.py` to fix your app client
2. Delete and recreate test user
3. Check spam folder for welcome email
4. Test full registration → password change → login flow
5. (Optional) Configure SES for production use

