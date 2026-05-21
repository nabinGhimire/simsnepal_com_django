# Verification Badges

Verification badges are a **separate concept** from email/mobile verification (OTP). Badges are granted after KYC/manual review/payment and have a validity period.

## Entities

- **User badge**: gives the user profile a verified badge.
- **Business badge**: gives the business profile a verified badge.
- **Channel badge**: gives a channel (business group) a verified badge (example: a renowned person’s channel).

## Data Model

Badges are stored in the `verifications` table as time-bounded “periods”:

- `verified_at`: when it was issued
- `verified_till`: when it expires (required)
- `next_reverify_at`: optional; defaults to mid-term between `verified_at` and `verified_till`
- `verified_by_user_id`: optional admin user who issued it
- `revoked_at` / `revoked_reason`: if manually revoked (example: payment failure, fraud, policy)
- `metadata`: optional (plan, payment reference, notes)

The badge is considered **active** when:
- `revoked_at IS NULL` AND `verified_till > now()`

## Lifecycle Scenarios

### Missed payment (badge drops)
- No special action required: when `verified_till` passes, the API stops returning `verified=true`.
- You can optionally call system revoke with `reason=payment_failed` to record an explicit revoke event.

### Renew after 3 months
- Issue a new verification period (system issue endpoint). Old records remain as history.

### Mid-term reverify
- The system stores `next_reverify_at` and a scheduled notifier can remind the owner when it is due.

## System API (business.hamro.com)

All endpoints require `X-System-API-Key`.

- Issue/renew: `POST /api/v1/system/verifications/issue`
- Revoke: `POST /api/v1/system/verifications/revoke`
- Expiring + reverify due: `GET /api/v1/system/verifications/expiring?days=14&include_reverify_due=1`
- History: `GET /api/v1/system/verifications/{verifiableType}/{verifiableId}`

## Notifications (WS + Push-style)

When a badge is issued/revoked/expiring/etc, the backend emits:

- **WebSocket event:** `verification.status`
- **Channels:**
  - `private-messenger.user.{user_id}`
  - `private-App.Models.User.{user_id}`
- **Push-style events:** emitted as `PushNotificationEvent` with `broadcastAs` like:
  - `verification.issued`, `verification.revoked`, `verification.expiring`, `verification.expired`, `verification.reverify_due`

## Scheduled reminders (server)

Use the notifier command in your scheduler/cron:

- `php artisan verifications:notify --expiring --days=14 --reverify --expired`

This command sets `*_notified_at` timestamps on the verification rows to avoid spamming.

## Firebase Push (FCM)

The backend listens to `PushNotificationEvent` and can deliver push notifications via FCM.

- Configure `FIREBASE_SERVER_KEY` in `.env` (legacy FCM API).
- Clients should send `fcm_token` and `platform` during `POST /auth/verify-otp` or `POST /auth/login` so the server can store per-device tokens.
