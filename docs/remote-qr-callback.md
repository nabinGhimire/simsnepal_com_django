# Remote QR Callback (External Website Login)

This project supports **external website** login/registration via QR code.

## Flow

1. Your website generates a QR code that encodes a callback URL like:
   - `https://your-site.com/auth/qr/scan/{token}/`
2. Your website shows the QR on a page and **polls** (or uses SSE/WebSocket) for completion using the same `{token}`.
3. The Hamro app scans the QR and sends the scanned string to:
   - `POST /api/v1/auth/qr/resolve` (requires the user to be logged in)
4. The API validates the callback URL and returns a **signed `identity_token` (JWT)** containing the current user's profile.
5. The delivery depends on `REMOTE_QR_MODE`:
   - `client` (recommended): the Hamro app POSTs the payload to your callback URL `POST /auth/qr/scan/{token}/`.
   - `server`: the Hamro backend POSTs the payload to your callback URL (requires strict host allowlisting).
6. Your website marks `{token}` as resolved and the QR page completes login/registration.

This design prevents spoofing (your website verifies the JWT signature) and avoids SSRF risk on this backend.

## API request (from mobile app)

`POST /api/v1/auth/qr/resolve`

```json
{
  "data": "https://127.0.0.1:8080/auth/qr/scan/Dbhp-ovsdVRk2wwcM4a7zwQTuG61vldfPKBWoeCMWug/"
}
```

## API response (what the app should forward)

The API responds with:

- `callback_url`
- `headers` to use
- `payload` containing `identity_token`
- `user` (for display convenience): the current user's basic profile
  - `id`, `name`, `full_name`, `username`
  - `avatar.sm|md|lg` (absolute URLs)

In `REMOTE_QR_MODE=client`, the app should immediately POST `payload` to `callback_url` with the suggested headers.
In `REMOTE_QR_MODE=server`, the backend will do that POST and this endpoint returns the upstream status.

Example (truncated):

```json
{
  "type": "remote_qr_callback",
  "delivery": "client",
  "callback_url": "https://your-site.com/auth/qr/scan/<token>/",
  "scan_token": "<token>",
  "user": {
    "id": "user-uuid",
    "name": "John Doe",
    "full_name": "John Doe",
    "username": "john_doe",
    "avatar": {
      "sm": "https://messengerin.hamro.com/storage/images/<user-uuid>/sm/<file>.png",
      "md": "https://messengerin.hamro.com/storage/images/<user-uuid>/md/<file>.png",
      "lg": "https://messengerin.hamro.com/storage/images/<user-uuid>/lg/<file>.png"
    }
  },
  "payload": {
    "identity_token": "header.payload.signature"
  }
}
```

## Callback request (to your website)

**Method:** `POST`

**Body (JSON):**

```json
{
  "event": "hamro.qr.resolve",
  "request_id": "uuid",
  "issued_at": "2026-05-03T09:00:00+00:00",
  "scan_token": "Dbhp-ovsdVRk2wwcM4a7zwQTuG61vldfPKBWoeCMWug",
  "callback_url": "https://127.0.0.1:8080/auth/qr/scan/Dbhp-ovsdVRk2wwcM4a7zwQTuG61vldfPKBWoeCMWug/",
  "identity_token": "header.payload.signature"
}
```

**Headers:**

- none required, but clients should send `Content-Type: application/json`

## Verifying `identity_token` (website)

Your website must verify the JWT signature (RS256) and then read user data from the JWT claims. Do not accept unsigned JSON fields as proof of identity.

Public keys are exposed as JWKS at:

- `GET /.well-known/hamro-jwks.json`

Claims include:

- `aud` = callback hostname
- `exp` = short TTL (default 60s)
- `scan_token` = the token from the QR code
- `user` = user profile payload (trusted after verifying signature)
  - includes `id`, `name`, `full_name`, `username`, and `avatar.sm|md|lg`

Recommended checks on your website:

- Verify JWT signature using JWKS
- Verify `iss` matches the expected Hamro backend (ex: `https://messengerin.hamro.com`)
- Verify `aud` matches your hostname (the callback URL host)
- Verify `exp` is not expired (keep TTL short)
- Verify `scan_token` exists in your DB and is unused, then mark it used (prevents replay)
- Enforce allowed algorithms (RS256 only). Do not trust `alg` from the token header.

## Django example (client website)

Install dependencies:

```bash
pip install pyjwt cryptography requests
```

Settings (example):

```python
# settings.py
HAMRO_JWKS_URL = "https://messengerin.hamro.com/.well-known/hamro-jwks.json"
HAMRO_ISSUER = "https://messengerin.hamro.com"
HAMRO_JWT_ALGS = ["RS256"]
```

Callback endpoint that receives the POST from the Hamro app:

```python
# views.py
import json
import requests
import jwt
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.db import transaction

JWKS_CACHE_KEY = "hamro_jwks"
JWKS_CACHE_TTL = 60 * 10

def get_hamro_jwks():
    jwks = cache.get(JWKS_CACHE_KEY)
    if jwks:
        return jwks
    resp = requests.get(settings.HAMRO_JWKS_URL, timeout=5)
    resp.raise_for_status()
    jwks = resp.json()
    cache.set(JWKS_CACHE_KEY, jwks, JWKS_CACHE_TTL)
    return jwks

def get_public_key_for_kid(kid: str):
    jwks = get_hamro_jwks()
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    raise ValueError("Unknown kid")

@csrf_exempt
@require_POST
def qr_scan_callback(request, token: str):
    """
    POST /auth/qr/scan/<token>/
    Body: { ..., "identity_token": "<jwt>" }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return HttpResponseBadRequest("Invalid JSON")

    identity_token = body.get("identity_token")
    if not identity_token:
        return HttpResponseBadRequest("Missing identity_token")

    unverified_header = jwt.get_unverified_header(identity_token)
    if unverified_header.get("alg") not in settings.HAMRO_JWT_ALGS:
        return HttpResponseBadRequest("Invalid alg")

    kid = unverified_header.get("kid")
    if not kid:
        return HttpResponseBadRequest("Missing kid")

    public_key = get_public_key_for_kid(kid)

    # aud is the callback hostname (no port). Use request host without port.
    expected_aud = request.get_host().split(":")[0].lower()

    try:
        claims = jwt.decode(
            identity_token,
            key=public_key,
            algorithms=settings.HAMRO_JWT_ALGS,
            issuer=settings.HAMRO_ISSUER,
            audience=expected_aud,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
            },
        )
    except jwt.PyJWTError:
        return HttpResponseBadRequest("Invalid identity_token")

    # Replay protection: token in URL must match scan_token claim.
    if claims.get("scan_token") != token:
        return HttpResponseBadRequest("Token mismatch")

    user_claims = claims.get("user") or {}
    hamro_user_id = claims.get("sub")
    email = user_claims.get("email")
    phone = user_claims.get("phone")

    # Example: resolve token in DB and mark used atomically.
    # Replace QrLoginToken with your model/table.
    from .models import QrLoginToken
    from django.utils import timezone

    with transaction.atomic():
        qr = QrLoginToken.objects.select_for_update().get(token=token)
        if qr.used_at is not None:
            return HttpResponseBadRequest("Token already used")
        qr.used_at = timezone.now()
        qr.hamro_user_id = hamro_user_id
        qr.payload = user_claims
        qr.save()

    # Now you can create/find a local user and start a session or return your own JWT.
    # (Implementation depends on your auth model.)

    return JsonResponse({"ok": True})
```

Suggested companion endpoint for the QR page to poll:

- `GET /auth/qr/status/<token>/` → `{ "status": "pending" }` or `{ "status": "resolved" }`

When `qr_scan_callback` marks the token as used, the polling endpoint can return resolved and provide whatever your frontend needs to finish login.

## Configuration

Configure this via `.env`:

- `REMOTE_QR_MODE` (`client` recommended)
- `REMOTE_QR_JWT_PRIVATE_KEY_PATH` / `REMOTE_QR_JWT_PUBLIC_KEY_PATH`
  - Recommended location: `storage/keys/remote-qr-private.pem` and `storage/keys/remote-qr-public.pem`
- `REMOTE_QR_REQUIRE_HTTPS` (recommended `true` in production)

If you switch to `REMOTE_QR_MODE=server`, the backend will POST to the callback URL itself; you must set `REMOTE_QR_ALLOWED_HOSTS` to a strict allowlist (SSRF protection).

After changing `.env` values, run `php artisan config:clear` (or `php artisan config:cache` again) so the new key paths take effect.

## When to use `REMOTE_QR_MODE=server`

Prefer `client` for “thousands of domains” because it avoids SSRF and doesn’t require an allowlist.

Use `server` only if you explicitly want the Hamro backend to call partner domains, and you can strictly control destinations via `REMOTE_QR_ALLOWED_HOSTS`.

If you truly have “thousands of domains”, keep `REMOTE_QR_MODE=client` so you don’t need any allowlist at all. Allowing the backend to POST to arbitrary domains is an SSRF risk and is not recommended.
