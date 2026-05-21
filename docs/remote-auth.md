# Remote Authentication (Login with Hamro)

ChatHamro provides a "Login with Hamro" feature for external applications.

## How it works
1. **Platform request**: Platform creates remote auth request using business API key.
2. **User approval**: User approves in Hamro app (direct request list or QR scan flow).
3. **Status polling/callback**: Platform checks status (or receives callback URL hit).
4. **Identity link**: On approval, Hamro creates/ensures `business_clients` mapping.

## Endpoints

### Platform-side (business.api middleware)

- `POST /api/v1/auth/remote-request`
  - Header: `X-Business-API-Key`
  - Creates pending request.
  - If no `user_identifier`, response includes `qr_code_url` (`hamro://auth/remote/{requestId}`) for QR flow.

- `GET /api/v1/auth/remote-status/{authRequest}`
  - Header: `X-Business-API-Key`
  - Returns request status and approved user details when available.

### User-side (auth:sanctum middleware)

- `GET /api/v1/auth/remote-requests`
  - Lists pending requests for logged-in user.

- `POST /api/v1/auth/remote-respond/{authRequest}`
  - Body: `{ "status": "approved" | "rejected" }`
  - Approves/rejects request.

- `POST /api/v1/auth/qr/resolve`
  - Universal QR resolver endpoint used by Hamro app scanner.
  - Remote website QR callbacks: returns a signed `identity_token` (JWT) and also includes `user.username` + `user.avatar.sm|md|lg` for UI display.
  - User UUID QR scans: returns `username` + `avatar.sm|md|lg`.
  - See: `docs/remote-qr-callback.md`

---
*Remote Auth Protocol*
