# Security Quick Reference Card

**For Developers** - Keep this handy while working on the codebase

---

## 🔐 Security Features You Now Have

### Rate Limiting
```php
// Applied to auth endpoints automatically
// 5 login attempts per minute per IP
// 60 API calls per minute per user/IP
```

### Security Headers
```
✓ X-Content-Type-Options: nosniff
✓ X-XSS-Protection: 1; mode=block
✓ X-Frame-Options: SAMEORIGIN
✓ Content-Security-Policy
✓ Strict-Transport-Security (HTTPS)
✓ Referrer-Policy
✓ Permissions-Policy
```

### Session Security
```php
'SESSION_ENCRYPT' => true,      // ✓ Enabled
'SESSION_SECURE' => true,       // ✓ HTTPS only
'SESSION_HTTP_ONLY' => true,    // ✓ No JavaScript access
'SESSION_SAME_SITE' => 'strict' // ✓ CSRF protected
```

### API Key Authentication
```php
// ✓ Uses constant-time comparison (prevents timing attacks)
// ✓ Logs failed attempts with IP
// ✓ No timing information leaked
```

---

## ⚠️ What NOT to Do

### ❌ Never Log Sensitive Data
```php
// BAD - Don't do this in production!
Log::info("User password: {$password}");
Log::info("OTP: {$otp}");
Log::info("API Key: {$apiKey}");

// GOOD - Only log non-sensitive info
Log::info("User login attempt", ['user_id' => $user->id]);
```

### ❌ Never Commit Credentials
```bash
# BAD - .env file committed
git add .env

# GOOD - Use .env.local for development
cp .env .env.local  # Don't commit .env.local
git add .env.example
```

### ❌ Never Use String Comparison for Keys
```php
// BAD - Timing attack vulnerability
if ($key !== $stored_key) {
    // vulnerable
}

// GOOD - Use hash_equals() or the timing-safe middleware
if (!hash_equals($key, $stored_key)) {
    // safe
}
```

### ❌ Never Trust User Input
```php
// BAD - SQL injection/XSS risk
$results = DB::select("SELECT * FROM users WHERE id = {$id}");

// GOOD - Use parameterized queries
$results = DB::select("SELECT * FROM users WHERE id = ?", [$id]);
// or
$results = User::where('id', $id)->get();
```

---

## ✅ What TO Do

### Enable Rate Limiting for New Auth Routes
```php
// In routes
Route::middleware('throttle:auth')->group(function () {
    Route::post('login', [AuthController::class, 'login']);
    Route::post('register', [AuthController::class, 'register']);
});
```

### Validate All Input
```php
$validated = $request->validate([
    'email' => ['required', 'email', 'max:255'],
    'password' => ['required', 'min:8', 'confirmed'],
    'name' => ['required', 'string', 'max:255'],
]);
```

### Use Blade Template Escaping
```blade
{{-- Good - Escaped by default --}}
<h1>{{ $user->name }}</h1>

{{-- Bad - Only use if you trust the source --}}
<h1>{!! $html_content !!}</h1>

{{-- Safe if using trusted HTML builder --}}
<h1>{!! Str::sanitizeHtml($content) !!}</h1>
```

### Hash Passwords Before Storage
```php
$user->password = Hash::make($request->password);
// Never store plain text passwords
```

### Use Environment Variables for Secrets
```php
// Good
$apiKey = config('app.system_api_key'); // Loaded from .env

// Bad
$apiKey = 'my_secret_key_12345'; // Hard-coded
```

### Log Security Events
```php
Log::warning('Failed authentication attempt', [
    'email' => $email,
    'ip' => request()->ip(),
    'user_agent' => request()->userAgent(),
]);
```

---

## 🛡️ Common Attack Vectors & Mitigation

### SQL Injection
```
Risk: Unparameterized queries
Fix: Always use parameterized queries or Eloquent ORM
Rate Limit: N/A
```

### XSS (Cross-Site Scripting)
```
Risk: Unescaped user input in views
Fix: Use {{ }} in Blade (auto-escaped)
Rate Limit: CSP header prevents inline scripts
```

### CSRF (Cross-Site Request Forgery)
```
Risk: Unauthorized state-changing requests
Fix: @csrf in forms, SameSite cookies
Rate Limit: Session tokens prevent replay
```

### Brute Force
```
Risk: Too many login attempts
Fix: Rate limiting (5 per minute per IP)
Monitor: Check logs for repeated failures
```

### Man-in-the-Middle
```
Risk: Unencrypted traffic
Fix: HTTPS enforced, HSTS header enabled
Monitor: Check certificate validity
```

### Information Disclosure
```
Risk: Debug info, stack traces, error details
Fix: APP_DEBUG=false, error sanitization
Monitor: Check error logs for sensitive data
```

---

## 📋 Security Checklist for New Features

Before adding new features:

- [ ] Validate all user input
- [ ] Use parameterized/Eloquent queries (no raw SQL)
- [ ] Escape output in views
- [ ] Add CSRF tokens to forms
- [ ] Check authorization (@can/@cannot)
- [ ] Rate limit if needed
- [ ] Don't log sensitive data
- [ ] Use HTTPS for external APIs
- [ ] Hash passwords with Hash::make()
- [ ] Review security implications
- [ ] Test with invalid/malicious input

---

## 🔍 Security Testing Commands

```bash
# Check security headers
curl -I https://yourdomain.com/

# Test rate limiting (login)
for i in {1..10}; do
  echo "Attempt $i"
  curl -X POST https://yourdomain.com/api/v1/auth/login \
    -d '{"login":"test","password":"test"}' \
    -H "Content-Type: application/json"
done

# Check for debug output
curl https://yourdomain.com/invalid-route

# Monitor logs for sensitive data
tail -f storage/logs/laravel.log | grep -i "password\|token\|key\|secret\|otp"

# Check HTTPS redirect
curl -I http://yourdomain.com/
```

---

## 🚨 Report Security Issues

If you find a security issue:

1. **Do NOT** post it publicly on GitHub/forums
2. **Do** notify the security team immediately
3. **Document** the exact steps to reproduce
4. **Provide** the impact assessment
5. **Never** exploit or share the vulnerability

---

## 📚 Key Configuration Files

- `config/security.php` - Security settings
- `config/session.php` - Session configuration
- `config/cors.php` - CORS settings
- `app/Http/Middleware/SecurityHeadersMiddleware.php` - HTTP headers
- `.env` - Environment variables (never commit!)
- `.env.example` - Template for .env (safe to commit)

---

## 💡 Remember

> **"Security is a shared responsibility"**

Every developer contributes to the security of the application.
- Write secure code
- Review security implications
- Stay updated on vulnerabilities
- Ask questions about security

**Questions? Check `docs/SECURITY_AUDIT_REPORT.md` or ask the security team.**
