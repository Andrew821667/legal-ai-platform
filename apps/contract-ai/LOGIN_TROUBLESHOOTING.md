# Login Troubleshooting Guide

**Created:** 2025-12-04
**Issue:** Cannot login with any credentials (neither demo nor backend)

---

## 🔍 Quick Diagnosis Steps

### Step 1: Test Demo Login Logic in Isolation

Open this URL in your browser:
```
http://localhost:3000/test-login.html
```

This is a standalone HTML page that tests the EXACT same demo credentials logic as the real login page.

**Try these credentials:**
- Email: `demo@example.com` Password: `demo123` (click "Quick Fill (demo)" button)
- Email: `admin@example.com` Password: `admin123` (click "Quick Fill (admin)" button)

**What to check:**
- ✅ If it shows "SUCCESS!" → Demo logic works, problem is in React/Next.js app
- ❌ If it shows "FAILED" → You may have typo in credentials (check for spaces)

---

### Step 2: Check Browser Console for Errors

1. Open http://localhost:3000/login
2. Press **F12** (or right-click → Inspect)
3. Click **Console** tab
4. Try to login with `demo@example.com` / `demo123`
5. Look for any **red error messages**

**Common errors:**
- `localStorage is not available` → Browser privacy settings blocking storage
- `Uncaught TypeError` → JavaScript error in the code
- `Failed to fetch` → Network error (shouldn't happen with demo mode)
- `Validation error` → React Hook Form validation failing

**Screenshot the console and share with developer!**

---

### Step 3: Check Network Tab (for API calls)

1. Still in Developer Tools (F12)
2. Click **Network** tab
3. Try to login with `demo@example.com` / `demo123`
4. Look for requests to `/api/v1/auth/login`

**What to check:**
- **No network requests** → Good! Demo mode should NOT call API
- **401 Unauthorized** → Means it tried the API instead of demo mode (BUG)
- **429 Too Many Requests** → Rate limited, need to wait

---

### Step 4: Check localStorage

1. In Developer Tools (F12)
2. Click **Application** tab (or **Storage** in Firefox)
3. Expand **Local Storage** → `http://localhost:3000`
4. Try to login with demo credentials
5. Check if `access_token` and `user` appear

**What to check:**
- ✅ If you see `access_token: "demo_token_..."` → Demo login WORKED
- ❌ If localStorage is empty → Login failed
- ❌ If you see error about localStorage → Browser blocking it

---

## 🐛 Known Issues & Solutions

### Issue #1: Demo Credentials Don't Work

**Symptoms:** Entering `demo@example.com` / `demo123` shows "Неверный email или пароль"

**Possible Causes:**
1. **Extra spaces in input:** Make sure no spaces before/after email or password
2. **Wrong email format validation:** React Hook Form may reject it
3. **JavaScript error:** Check console (Step 2)
4. **localStorage blocked:** Check Application tab (Step 4)

**Solution:**
- Use the test page (http://localhost:3000/test-login.html) to verify logic
- Check browser console for errors
- Try different browser (Chrome, Firefox, Safari)
- Disable browser extensions that might block JavaScript

---

### Issue #2: Backend Credentials Don't Work

**Symptoms:** Entering `admin@contractai.local` / `Admin123!` shows "Неверный email или пароль"

**Possible Causes:**
1. **Wrong password:** Passwords in database don't match documentation
2. **Account locked:** After 5 failed attempts, account locks for 30 minutes
3. **Backend not running:** Check if http://localhost:8000 works

**Solution A: Check if backend is running**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

**Solution B: Check backend logs**
```bash
tail -50 logs/backend.log
# Look for "user_not_found" or "invalid_password"
```

**Solution C: Unlock admin account**
```bash
cd /Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman
sqlite3 contract_ai.db "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE email = 'admin@contractai.local';"
```

**Solution D: Reset admin password**
```bash
# Coming soon - need to fix bcrypt compatibility issue first
```

---

### Issue #3: Page Reloads or Doesn't Redirect

**Symptoms:** Click "Войти" button but nothing happens, or page reloads

**Possible Causes:**
1. **Form validation error:** React Hook Form blocking submission
2. **JavaScript error:** Check console
3. **Router navigation failed:** Next.js issue

**Solution:**
- Check console for validation errors
- Make sure email format is valid (has @)
- Make sure password is at least 6 characters
- Check Network tab - is form even submitting?

---

## 📋 Credential Reference

### Frontend Demo Credentials (Work WITHOUT backend)

These credentials work purely in the browser, no API call needed:

| Email | Password | Role | Should Work? |
|-------|----------|------|-------------|
| demo@example.com | demo123 | demo | ✅ YES |
| admin@example.com | admin123 | admin | ✅ YES |
| lawyer@example.com | lawyer123 | lawyer | ✅ YES |
| junior@example.com | junior123 | junior_lawyer | ✅ YES |

**How to test:** Use http://localhost:3000/test-login.html

---

### Backend Database Credentials (Require backend API)

These credentials require the backend API to be running:

| Email | Password | Role | Status |
|-------|----------|------|--------|
| admin@contractai.local | Admin123! | admin | ⚠️ UNKNOWN (may be wrong password) |
| lawyer@contractai.local | Lawyer123! | lawyer | ⚠️ UNKNOWN (may be wrong password) |
| junior@contractai.local | Junior123! | junior_lawyer | ⚠️ UNKNOWN (may be wrong password) |
| senior@contractai.local | *Unknown* | senior_lawyer | ❌ Password unknown |

**Status:** Backend authentication is currently broken - password hashes don't match expected passwords.

---

## 🔧 Advanced Debugging

### Check Login Page Code

The demo credentials check happens in this file:
```
frontend/src/app/login/page.tsx
Lines 16-51
```

Key logic:
```typescript
const demoUser = demoCredentials.find(
  u => u.email === data.email && u.password === data.password
)

if (demoUser) {
  // Demo mode - bypass API
  localStorage.setItem('access_token', 'demo_token_' + Date.now())
  router.push('/dashboard')
  return
}

// If not demo, try real API...
```

### Check API Service Code

The backend API calls happen in this file:
```
frontend/src/services/api.ts
Lines 151-172
```

---

## ✅ Verification Checklist

Run through this checklist to diagnose the issue:

- [ ] Frontend is running (http://localhost:3000 loads)
- [ ] Backend is running (http://localhost:8000/health returns healthy)
- [ ] Test page works (http://localhost:3000/test-login.html shows success)
- [ ] Browser console has no errors (F12 → Console tab)
- [ ] localStorage is accessible (F12 → Application tab)
- [ ] No validation errors on form (email format, password length)
- [ ] Tried in different browser (Chrome, Firefox, Safari)
- [ ] Cleared browser cache and cookies
- [ ] No browser extensions blocking JavaScript

---

## 🆘 Still Can't Login?

If you've tried everything above and still can't login:

1. **Share this information:**
   - Browser name and version
   - Screenshot of browser console (F12 → Console)
   - Screenshot of Network tab when submitting form
   - What exact error message you see
   - Whether test page (test-login.html) works or not

2. **Temporary workaround:**
   - Use the test page to verify logic works
   - Manually add tokens to localStorage:
     ```javascript
     // Open browser console (F12) on http://localhost:3000
     localStorage.setItem('access_token', 'demo_token_123')
     localStorage.setItem('user', JSON.stringify({
       name: 'Demo User',
       email: 'demo@example.com',
       role: 'demo'
     }))
     // Then go to http://localhost:3000/dashboard
     ```

3. **Get developer logs:**
   ```bash
   # Frontend logs
   tail -50 /Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman/logs/frontend.log

   # Backend logs
   tail -50 /Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman/logs/backend.log
   ```

---

## 📊 Current Status Summary

**Frontend:**
- ✅ Running on port 3000
- ✅ Login page loads correctly
- ✅ Demo credentials defined in code
- ⚠️ Unknown why demo login fails for user

**Backend:**
- ✅ Running on port 8000
- ✅ API health endpoint works
- ❌ Authentication broken (password hashes don't match)
- ⚠️ Admin account was locked (now unlocked)

**Next Steps:**
1. Test with http://localhost:3000/test-login.html
2. Check browser console for errors
3. Share console output and error messages
4. Try manual localStorage workaround if needed

---

**Last Updated:** 2025-12-04
**File Location:** `/Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman/LOGIN_TROUBLESHOOTING.md`
