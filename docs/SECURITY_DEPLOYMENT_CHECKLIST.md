# Security Deployment Checklist

Use this checklist when deploying the security updates to ensure all fixes are properly applied.

## Pre-Deployment

- [ ] Read `SECURITY_AUDIT_REPORT.md` completely
- [ ] Back up database
- [ ] Back up .env file
- [ ] Verify all environment variables are correct
- [ ] Review changes in git diff

## Environment Configuration

- [ ] Update `.env` with production settings
- [ ] Set `APP_DEBUG=false`
- [ ] Set `APP_ENV=production`
- [ ] Set `SESSION_ENCRYPT=true`
- [ ] Generate new `SYSTEM_API_KEY` (strong random value)
- [ ] Update `REVERB_APP_KEY` and `REVERB_APP_SECRET`
- [ ] Update `POSTAL_API_KEY` 
- [ ] Ensure `APP_URL` is HTTPS
- [ ] Set `SESSION_DOMAIN` to production domain
- [ ] Verify all database credentials

## Cache Clearing

- [ ] Clear application cache: `php artisan cache:clear`
- [ ] Clear config cache: `php artisan config:clear`
- [ ] Clear route cache: `php artisan route:clear`
- [ ] Clear view cache: `php artisan view:clear`
- [ ] Or run: `php artisan optimize:clear` (clears all)

## Testing Before Deployment

- [ ] Test login functionality
- [ ] Test OTP verification
- [ ] Test password reset
- [ ] Verify no sensitive data in logs
- [ ] Check error pages don't expose stack traces
- [ ] Test API endpoints with rate limiting
- [ ] Verify security headers are present: `curl -I https://yourdomain.com/`

## Deployment Steps

1. [ ] Pull latest code changes
2. [ ] Run `composer install --no-dev` (if needed)
3. [ ] Run `php artisan migrate --force` (if needed)
4. [ ] Clear all caches (see Cache Clearing section above)
5. [ ] Restart PHP-FPM or application server
6. [ ] Verify application is running
7. [ ] Monitor error logs for issues

## Post-Deployment Verification

- [ ] Application loads successfully
- [ ] No errors in logs
- [ ] Security headers present in responses
- [ ] Rate limiting is working (test by making 6+ auth requests)
- [ ] Login works with rate limiting
- [ ] API endpoints return 429 on excessive requests
- [ ] No debug information exposed in errors
- [ ] Verify HTTPS certificate is valid
- [ ] Check that cookies have secure flags

## Security Actions

- [ ] Rotate all API keys immediately
- [ ] Review access logs for suspicious activity
- [ ] Audit user accounts for unauthorized access
- [ ] Update password policies in documentation
- [ ] Notify team of security updates

## Monitoring

- [ ] Monitor application logs
- [ ] Monitor failed authentication attempts
- [ ] Monitor for 429 rate limit responses
- [ ] Check database queries don't expose credentials
- [ ] Verify no OTP values in logs

## Rollback Plan (if issues occur)

- [ ] Restore previous .env file
- [ ] Restore previous code from git
- [ ] Restore database backup
- [ ] Clear caches and restart

## Documentation

- [ ] Update deployment guide with new steps
- [ ] Document API key rotation procedure
- [ ] Update security policy documentation
- [ ] Train team on security best practices
- [ ] Schedule next security audit (e.g., 3 months)

## Sign-Off

- [ ] Deployment tested successfully
- [ ] No critical issues found
- [ ] Approved by: _________________________ Date: _____________
- [ ] Deployment completed at: _________________________ (time)

---

## Quick Reference: Commands

```bash
# Clear all caches
php artisan optimize:clear

# View logs
tail -f storage/logs/laravel.log

# Test rate limiting
for i in {1..10}; do
  curl -X POST http://localhost/api/v1/auth/login \
    -d '{"login":"test@test.com","password":"test"}' \
    -H "Content-Type: application/json"
done

# Check security headers
curl -I https://yourdomain.com/

# Verify no APP_DEBUG info
# Should see generic error page, not stack trace
curl https://yourdomain.com/invalid-route
```

---

## Additional Resources

- Laravel Security Documentation: https://laravel.com/docs/security
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Laravel Security Advisories: https://laravel.com/advisories
