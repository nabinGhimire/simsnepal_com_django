# ChatHamro Developer API Documentation

This document provides a comprehensive guide to the ChatHamro API endpoints for mobile (Android & iOS) application development.

## Base URLs

**API Server Base URL:** `https://messengerin.hamro.com/api/v1`
All REST API requests should be prefixed with this base URL.

**WebSocket Server URL:** 
- Reverb: `wss://{REVERB_HOST}` (recommended)
- Or use Laravel Echo for real-time connections.

## Authentication

The API uses **Laravel Sanctum** for token-based authentication. For protected routes, you must include the access token in the `Authorization` header of your HTTP requests:

```http
Authorization: Bearer {your_access_token}
```
All API requests must also include the following headers for proper JSON handling:
```http
Accept: application/json
Content-Type: application/json
```

---

## 1. Auth Endpoints

These endpoints are responsible for user registration, login, and token generation.

### 1.1 User Registration
**Endpoint:** `POST /auth/register`
**Description:** Registers a new user and generates an OTP for account verification.

**Request Payload:**
```json
{
  "first_name": "John",
  "middle_name": "Doe",    // (Optional)
  "last_name": "Smith",
  "username": "john1234", // (Optional; if omitted, generated as firstname + 4 digits)
  "email": "john@example.com", // (Required if mobile_number is empty)
  "mobile_number": "9800000000", // (Required if email is empty)
  "password": "SecurePassword123",
  "password_confirmation": "SecurePassword123"
}
```

**Success Response (200 OK):**
```json
{
  "message": "Registration successful. Please verify your account with the OTP sent.",
  "user_id": 1,
  "otp_required": true,
  "mock_otp": "123456" // Included ONLY in local environments for testing
}
```

### 1.2 Verify OTP
**Endpoint:** `POST /auth/verify-otp`
**Description:** Verifies the OTP sent to the user. Generates an access token upon success.

**Request Payload:**
```json
{
  "user_id": 1,
  "otp": "123456",
  "device_identifier": "unique-device-uuid", // (Optional but recommended for mobile apps)
  "device_name": "iPhone 14 Pro",           // (Optional)
  "platform": "ios",                        // (Optional: ios|android|web)
  "fcm_token": "FCM_TOKEN_HERE"             // (Optional: for push notifications)
}
```

**Success Response (200 OK):**
```json
{
  "message": "Account verified effectively.",
  "access_token": "1|abcdef1234567890...",
  "token_type": "Bearer",
  "device_identifier": "unique-device-uuid"
}
```

### 1.3 Login
**Endpoint:** `POST /auth/login`
**Description:** Authenticates a user. If logging in from a new/unverified device, it triggers an OTP flow.

**Request Payload:**
```json
{
  "login": "john@example.com", // Can be email, mobile_number, or username
  "password": "SecurePassword123",
  "device_identifier": "unique-device-uuid", // Crucial for skipping OTP on recognized devices
  "device_name": "iPhone 14 Pro",            // Optional
  "platform": "ios",                         // Optional: ios|android|web
  "fcm_token": "FCM_TOKEN_HERE"              // Optional: for push notifications
}
```

**Success Response (Recognized Device - 200 OK):**
```json
{
  "access_token": "2|abcdef123456...",
  "token_type": "Bearer",
  "device_identifier": "unique-device-uuid"
}
```

### 1.4 Logout
**Endpoint:** `POST /auth/logout`
**Description:** Revokes the current access token. Requires authentication.

**Response (200 OK):**
```json
{
  "message": "Logged out successfully."
}
```

### 1.5 Forgot Password & Reset
**Forgot Password Endpoint:** `POST /auth/forgot-password`
**Payload:** `{ "email": "john@example.com" }`

**Reset Password Endpoint:** `POST /auth/reset-password`
**Payload:**
```json
{
  "email": "john@example.com",
  "otp": "123456",
  "password": "NewSecurePassword123",
  "password_confirmation": "NewSecurePassword123"
}
```

### 1.6 Login with Hamro (Remote Authentication Concept)
**Concept:** External apps authenticate users via Hamro identity and user approval inside Hamro app.

#### Remote Auth API flow
1. Platform creates request: `POST /auth/remote-request` (with `X-Business-API-Key`, no bearer token required). `user_identifier` supports email/mobile/username.
2. User approves/rejects in Hamro app:
   - pending list: `GET /auth/remote-requests`
   - response: `POST /auth/remote-respond/{authRequest}`
3. Platform checks result: `GET /auth/remote-status/{authRequest}` (with `X-Business-API-Key`, no bearer token required).
4. Optional callback is sent to `callback_url` when status changes.

#### QR flow
- Platform can create request without `user_identifier`.
- API returns `qr_code_url` in deep-link form `hamro://auth/remote/{requestId}`.
- Hamro app scans and resolves QR via `POST /auth/qr/resolve`.
  - For remote website QR callbacks, the resolve response includes a signed `identity_token` (JWT) and also returns `user.full_name` + `user.username` + `user.avatar.sm|md|lg` for display.
  - For user QR (UUID) scans, the response includes `name` + `full_name` + `username` + `avatar.sm|md|lg`.

---

## 2. Business & Platform APIs

These endpoints are used by businesses and platforms to interact with the ChatHamro ecosystem.

### 2.1 System Management (Admin Only)
Used by the central management portal (`business.hamro.com`) to sync business data.
- **Endpoint:** `POST /system/businesses/sync`
- **Header:** `X-System-API-Key: {SYSTEM_API_KEY}`
- **Description:** Creates or updates a business and returns its default API key.
- **Payload:**
  ```json
  {
    "user_id": "owner-uuid",
    "name": "Acme Corp",
    "type": "company", // platform, company, individual
    "website": "https://acme.com",
    "contact_email": "contact@acme.com",
    "contact_phone": "+9779800000000",
    "contact_name": "Acme Support",
    "address": "Kathmandu, Nepal",
    "metadata": { "notes": "nullable fields are allowed" },
    "is_active": true
  }
  ```

#### 2.1.1 Verification Badges (Admin Only)
Verification badges are **not** email/mobile verification. They are paid/KYC/manual badges with an expiry (`verified_till`) and reverify window.

All endpoints require: `X-System-API-Key: {SYSTEM_API_KEY}`.

**Issue / Renew a badge**
- **Endpoint:** `POST /system/verifications/issue`
- **Behavior:** Creates a new verification period and revokes any currently-active badge for the same `badge`/entity.
- **Payload:**
  ```json
  {
    "verifiable_type": "business", // user, business, channel
    "verifiable_id": "uuid",
    "badge": "verified",
    "verified_by_user_id": "admin-user-uuid", // optional
    "verified_till": "2026-12-31T23:59:59Z",
    "next_reverify_at": "2026-08-01T00:00:00Z", // optional; default = mid-term
    "source": "payment",
    "metadata": { "plan": "verified_badge" }
  }
  ```
- **Notifications:** emits WS + Push-style events (see WebSockets section).

**Revoke a badge**
- **Endpoint:** `POST /system/verifications/revoke`
- **Payload:**
  ```json
  {
    "verifiable_type": "business",
    "verifiable_id": "uuid",
    "badge": "verified",
    "reason": "payment_failed"
  }
  ```

**Get active + history**
- **Endpoint:** `GET /system/verifications/{verifiableType}/{verifiableId}`
- Example: `GET /system/verifications/business/{businessId}`

**List expiring / reverify-due**
- **Endpoint:** `GET /system/verifications/expiring?days=14&include_reverify_due=1`

**Scheduler reminders (server-side)**
- Command: `php artisan verifications:notify --expiring --days=14 --reverify --expired`
- Use this to notify owners before/at expiry (payment reminders) and at mid-term reverify time.

### 2.2 Business API (External Notifications)
Used by external apps/platforms to send real-time notifications to users.
- **Endpoint:** `POST /business-api/notifications`
- **Header:** `X-Business-API-Key: bsk_your_key_here`
- **Description:** Sends text or attachment messages to a specific user or a pre-defined business group.
- **Payload:**
  ```json
  {
    "user_id": "target-user-uuid",
    "message": "Your order #123 has been shipped!",
    "subject": "Order Update" // Optional
  }
  ```

#### Attachment payloads (multipart/form-data)

**Image notification**
```http
POST /business-api/notifications
X-Business-API-Key: bsk_xxx
Content-Type: multipart/form-data
```
Fields:
- `user_id` or `external_client_id`
- `image` (file)

**Document/file notification**
```http
POST /business-api/notifications
X-Business-API-Key: bsk_xxx
Content-Type: multipart/form-data
```
Fields:
- `user_id` or `external_client_id`
- `document` (file)

### 2.3 Platform Authorization
Platforms can request permission to send messages on behalf of other companies.
- **Request Authorization:** `POST /businesses/{platform_id}/request-authorization`
- **Respond to Request:** `POST /company-platform/authorizations/{auth_id}/respond`

#### Delegated on-behalf keys
After approval, business can issue platform-owned delegated keys:

- **Create delegated key:** `POST /businesses/{business}/api-keys/delegated`
- **List delegated keys:** `GET /businesses/{business}/api-keys/delegated`

Create payload example:
```json
{
  "platform_business_id": "platform-uuid",
  "name": "Amazon on behalf of Apple",
  "service_name": "simsnepal",
  "scopes": ["messages:send"],
  "expires_at": "2026-12-31T23:59:59Z"
}
```

Notes:
- `service_name` identifies the external service (example: `simsnepal`).
- Exactly one API key is allowed per `service_name` in a scope:
  - direct key scope: `{business_id}`
  - delegated key scope: `{platform_business_id + on_behalf_of_business_id}`

---

### 2.4 Business API Key management (System app: business.hamro.com)

These endpoints are used by the **system app** (`business.hamro.com`) to create, rotate, and manage API keys for businesses.

- **Header:** `X-System-API-Key: {SYSTEM_API_KEY}`

**List keys**
- `GET /system/businesses/{business}/api-keys`

**Create key**
- `POST /system/businesses/{business}/api-keys`
- Payload example:
```json
{
  "name": "My Service Key",
  "service_name": "simsnepal",
  "scopes": ["messages:send"],
  "expires_at": "2026-12-31T23:59:59Z"
}
```
Notes:
- `name` or `service_name` is required (at least one).
- `service_name` is normalized (lowercased and non-alphanumerics removed).
- Only one key per `service_name` is allowed within the same scope.

**View key**
- `GET /system/businesses/{business}/api-keys/{apiKey}`

**Update key (metadata / status)**
- `PATCH /system/businesses/{business}/api-keys/{apiKey}`

**Regenerate key**
- `POST /system/businesses/{business}/api-keys/{apiKey}/regenerate`

**Delete key**
- `DELETE /system/businesses/{business}/api-keys/{apiKey}`

**Delegated platform keys (on behalf of business)**

After approval, the system app can issue platform-owned delegated keys for a specific business:

- **List delegated keys:** `GET /system/businesses/{business}/api-keys/delegated`
- **Create delegated key:** `POST /system/businesses/{business}/api-keys/delegated`

Create payload example:
```json
{
  "platform_business_id": "platform-uuid",
  "name": "SimsNepal delegated key",
  "service_name": "simsnepal",
  "scopes": ["groups:manage", "messages:send"],
  "expires_at": "2026-12-31T23:59:59Z"
}
```

---

### 2.5 Platform group/channel management (Platform app: simsnepal.com)

Platforms use a **delegated platform key** (`key_type=platform`, `on_behalf_of_business_id` set) to create channels/groups and manage members for the business.

- **Header:** `X-Business-API-Key: bsk_...` (delegated platform key)

**List groups/channels**
- `GET /business-api/groups`

**Create group/channel**
- `POST /business-api/groups`
```json
{
  "name": "Team Alpha",
  "description": "Optional",
  "group_type": "group"
}
```

**View/update/delete**
- `GET /business-api/groups/{group}`
- `PATCH /business-api/groups/{group}`
- `DELETE /business-api/groups/{group}`

**Member management**
- `GET /business-api/groups/{group}/members`
- `POST /business-api/groups/{group}/members`
```json
{
  "user_id": "user-uuid"
}
```
or:
```json
{
  "external_client_id": "platform-user-id"
}
```
- `DELETE /business-api/groups/{group}/members/{memberId}`

## 3. Key Modules

ChatHamro utilizes `rtippin/messenger`. Below are the primary endpoints and payloads.

### 2.1 Viewing Threads & Chats

- **Get Unread Count:** `GET /unread-threads-count`
- **List Groups:** `GET /groups`
- **List Private Chats:** `GET /privates`
- **Get Thread Messages:** `GET /threads/{thread}/messages`
  **(Response includes paginated array of messages)**

### 2.2 Creating Chats
**Create Private Chat**
**Endpoint:** `POST /privates`
**Payload:**
```json
{
  "recipient_id": "user-uuid-or-id",
  "recipient_alias": "user", // The morph alias (usually "user")
  "message": "Hello! Let's chat." // Initial message
}
```

**Create Group Chat**
**Endpoint:** `POST /groups`
**Payload:**
```json
{
  "subject": "Friends Group",
  "providers": [
    {
      "id": "provider-uuid",
      "alias": "user"    
    }
  ]
}
```

### 2.3 Sending Messages
**Send Text Message**
**Endpoint:** `POST /threads/{thread}/messages`
**Payload:**
```json
{
  "message": "Hello world!",
  "temporary_id": "client-side-uuid" // Optional, helps sync UI before server responds
}
```

**Send Image Message**
**Endpoint:** `POST /threads/{thread}/images`
**Headers:** `Content-Type: multipart/form-data`
**Payload (Form Data):**
- `image`: [File Blob] (Required)
- `temporary_id`: "client-side-uuid" (Optional)

**Send Document / Audio / Video Message**
Same structure as above, changing endpoint to `/documents`, `/audio`, or `/videos` and changing the file key to `document`, `audio`, or `video`.

**Mark Thread Read**
**Endpoint:** `GET /threads/{thread}/mark-read`
(No payload, marks all messages in the thread as read for the authenticated user)

### 2.4 Audio/Video Calls
- **Get Active Calls:** `GET /active-calls`
- **Join Call:** `POST /threads/{thread}/calls/{call}/join`
- **Leave Call:** `POST /threads/{thread}/calls/{call}/leave`
- **End Call:** `POST /threads/{thread}/calls/{call}/end`

(No specific body payloads required for the above call actions except the Thread ID and Call ID in the URL)

### 2.5 Friends System
- **Get Friends:** `GET /friends`
- **Pending Requests:** `GET /friends/pending`
- **Sent Requests:** `GET /friends/sent`
- **Remove Friend:** `DELETE /friends/{friend}`

**Send Friend Request (Store Sent Request)**
**Endpoint:** `POST /friends/sent`
**Payload:**
```json
{
  "recipient_id": "user-uuid-or-id",
  "recipient_alias": "user"
}
```

**Accept Friend Request**
**Endpoint:** `PUT /friends/pending/{pending}`
**Description:** Accepts a friend request you received. The `{pending}` parameter is the ID of the pending request.
(No payload required)

**Deny/Reject Friend Request**
**Endpoint:** `DELETE /friends/pending/{pending}`
**Description:** Denies a pending friend request you received.
(No payload required)

**Cancel Sent Friend Request**
**Endpoint:** `DELETE /friends/sent/{sent}`
**Description:** Cancels a friend request you have sent to someone else.
(No payload required)

### 2.6 User Settings & Profiles
**Update Avatar**
**Endpoint:** `POST /avatar`
**Headers:** `Content-Type: multipart/form-data`
**Payload (Form Data):**
- `image`: [File Blob] (Required)

**Verification badge fields (separate from email/mobile verification)**
- Provider payloads now include:
  - `verified` (boolean)
  - `verification.flags.account_verified` (user badge)
  - `verification.flags.business_verified` (business badge)
  - `verification.flags.channel_verified` (always false for providers)
  - `verification.status` (`active|expired|revoked|none`)
  - `verification.verified_at`, `verification.verified_till`, `verification.next_reverify_at`
  - `verification.verified_by` (`{id,name}` or `null`)
  - `verification.is_recent` (boolean)
- Thread payloads now include:
  - `verified` (boolean)
  - `channel_verified`, `business_verified`
  - `verification.flags.business_verified`, `verification.flags.channel_verified`
  - `verification.channel` and `verification.business` (verification period details)

---

## 3. Real-time Broadcasting (WebSockets)

To build a fully real-time experience, mobile apps must connect to our WebSocket server using a Laravel Echo compatible client.

**WebSocket URL:** `wss://aprilin.hamro.com`
**Authentication:** Use the Bearer token generated from standard authentication.

### Recommended Laravel Echo Configuration (Pusher/Reverb):
```json
{
    "broadcaster": "pusher",
    "key": "[REDACTED_REVERB_APP_KEY]", // Reverb App Key
    "wsHost": "aprilin.hamro.com",
    "wsPort": 443,
    "wssPort": 443,
    "forceTLS": true,
    "disableStats": true,
    "authEndpoint": "https://messengerin.hamro.com/api/v1/broadcasting/auth",
    "auth": {
        "headers": {
            "Authorization": "Bearer {your_token}"
        }
    }
}
```

### Channels
- **User Channel:** `private-messenger.user.{user_id}` (Listens to new friend requests, new threads, updates)
- **Thread Channel:** `presence-messenger.thread.{thread_id}` (Listens to messages, calls, read receipts, and typing indicators within a specific thread)

### Verification Badge Events (WebSocket + Push-style)
When a verification badge is issued/revoked/expiring/etc, the backend emits:

**WebSocket**
- **Event name:** `verification.status`
- **Channels:**
  - `private-messenger.user.{user_id}` (recommended for clients already using messenger channels)
  - `private-App.Models.User.{user_id}` (system channel)
- **Payload (example keys):**
  - `action`: `issued|revoked|expiring|expired|reverify_due`
  - `badge`, `status`, `verified_at`, `verified_till`, `next_reverify_at`, `revoked_reason`, `source`

**Push-style (server event)**
- Emitted as `PushNotificationEvent` with `broadcastAs`:
  - `verification.issued`, `verification.revoked`, `verification.expiring`, `verification.expired`, `verification.reverify_due`
- This is meant to plug into FCM/APNs later (no direct FCM sender is included yet).

---

## 4. Developer Guide: Implementing Business Logic

For backend developers extending ChatHamro, business logic is organized using the **Action Pattern**. This ensures logic is decoupled from Controllers and Models.

### 4.1 The Action Pattern
All core business logic should be placed in the `app/Actions` directory.

- **Base Class:** All actions must extend `App\Actions\BaseMessengerAction`.
- **Execution:** Actions typically implement an `execute()` method that handles:
  - Data validation/setup.
  - Database transactions (using `$this->database->transaction()`).
  - Logic execution (usually in a protected `handle()` method).
  - Finalization (firing events and broadcasts).

**Example usage in a Controller:**
```php
public function store(Request $request, Thread $thread, StoreMessage $storeMessage)
{
    $storeMessage->execute($thread, $request->all());
    return $storeMessage->getJsonResource();
}
```

### 4.2 Bot Logic
Bot behaviors are implemented as "Handlers".
- **Directory:** `app/Bots/Handlers` (or as configured in `MessengerBots`).
- **Base Class:** Must extend `App\Support\BotActionHandler`.
- **Required Methods:**
  - `getSettings()`: Defines the bot's alias, name, and triggers.
  - `handle()`: The actual logic executed when the bot is triggered.

### 4.3 Best Practices
- **Use Actions:** Never put complex business logic directly in Controllers.
- **Transactions:** Use the built-in transaction support in `BaseMessengerAction` to ensure data integrity.
- **Events:** Leverage the automatic event dispatching in Actions to keep the frontend in sync via WebSockets.

---

## 5. In-App Notifications

This section covers in-app notification management (separate from push notifications).

### 5.1 List Notifications
**Endpoint:** `GET /auth/notifications`

**Headers:**
```http
Authorization: Bearer {your_access_token}
Accept: application/json
```

**Success Response (200 OK):**
```json
{
  "data": [
    {
      "id": "notification-uuid",
      "type": "friend_request",
      "title": "New Friend Request",
      "body": "John Doe sent you a friend request.",
      "image": "https://...",
      "route": "/friend-request/abc123",
      "read_at": null,
      "created_at": "2024-01-15T10:30:00Z",
      "data": {
        "sender_id": "user-uuid",
        "sender_name": "John Doe",
        "request_id": "abc123"
      }
    }
  ],
  "meta": {
    "current_page": 1,
    "total": 10
  }
}
```

### 5.2 Get Unread Count
**Endpoint:** `GET /auth/notifications/unread-count`

**Success Response (200 OK):**
```json
{
  "count": 5
}
```

### 5.3 Mark All as Read
**Endpoint:** `POST /auth/notifications/mark-all-read`

**Success Response (200 OK):**
```json
{
  "success": true
}
```

### 5.4 Mark Single as Read
**Endpoint:** `POST /auth/notifications/{notification_id}/mark-read`

**Success Response (200 OK):**
```json
{
  "success": true
}
```

### 5.5 Handle Notification Action (Accept/Decline)
**Endpoint:** `POST /auth/notifications/action`

**Request Payload:**
```json
{
  "notification_id": "notification-uuid",
  "action": "accept"  // or "decline"
}
```

**Supported Actions by Type:**

| Notification Type | Accept | Decline |
|-------------------|--------|---------|
| `friend_request` | Creates friendship + chat thread | Deletes pending request |
| `group_join_request` | Adds user to group | No action |
| `channel_join_request` | Adds user to channel | No action |
| `added_to_group` | Marks as read | Marks as read |
| `added_to_channel` | Marks as read | Marks as read |
| `group_join_approved` | Marks as read | Marks as read |
| `group_join_rejected` | Marks as read | Marks as read |
| `plain` | Marks as read | Marks as read |
| `system` | Marks as read | Marks as read |

**Success Response (200 OK):**
```json
{
  "success": true
}
```

### 5.6 Handle FCM Push Notification Action
**Endpoint:** `POST /auth/notifications/fcm-action`

This endpoint is for mobile apps to handle FCM push notification action button clicks (Accept Friend, Reject Friend, etc.).

**Headers:**
```http
Authorization: Bearer {your_access_token}
Content-Type: application/json
```

**Request Payload:**
```json
{
  "action": "accept_friend",  // or "reject_friend", "allow_group_join", "reject_group_join", "allow_channel_join", "reject_channel_join", "accept_login", "reject_login"
  "type": "friend_request",  // or "group_join_request", "channel_join_request", "multi_device_login"
  "request_id": "request-uuid",  // if applicable
  "sender_id": "sender-uuid",  // if applicable
  "group_id": "group-uuid",  // if applicable
  "channel_id": "channel-uuid",  // if applicable
  "new_device_id": "device-id",  // for multi-device login
  "user_id": "user-uuid"  // for multi-device login
}
```

**Supported Actions by Type:**

| Notification Type | Actions |
|-------------------|---------|
| `friend_request` | `accept_friend`, `reject_friend` |
| `group_join_request` | `allow_group_join`, `reject_group_join` |
| `channel_join_request` | `allow_channel_join`, `reject_channel_join` |
| `multi_device_login` | `accept_login`, `reject_login` |

**Success Response (200 OK):**
```json
{
  "message": "Friend request accepted.",
  "thread_id": "thread-uuid"  // if applicable
}
```

**Error Responses:**
- `400`: Missing required fields
- `403`: Not authorized (e.g., not group admin)
- `404`: Resource not found (e.g., friend request not found)
- `500`: Action failed

### 5.7 Delete Notification
**Endpoint:** `DELETE /auth/notifications/{notification_id}`

**Success Response (200 OK):**
```json
{
  "success": true
}
```

### 5.8 Delete All Notifications
**Endpoint:** `DELETE /auth/notifications/all`

**Success Response (200 OK):**
```json
{
  "success": true
}
```

---

## 6. Device Management (FCM Tokens)

### 6.1 Register FCM Token
**Endpoint:** `POST /devices/fcm-token`

**Request Payload:**
```json
{
  "device_identifier": "unique-device-uuid",
  "fcm_token": "YOUR_FCM_TOKEN_HERE",
  "device_name": "iPhone 15 Pro",
  "platform": "ios"
}
```

**Success Response (200 OK):**
```json
{
  "message": "FCM token registered successfully.",
  "device_id": "device-uuid"
}
```

### 6.2 Remove FCM Token
**Endpoint:** `DELETE /devices/fcm-token`

**Request Payload:**
```json
{
  "device_identifier": "unique-device-uuid"
}
```

### 6.3 List Devices
**Endpoint:** `GET /devices`

**Success Response (200 OK):**
```json
{
  "devices": [
    {
      "id": "device-uuid",
      "device_name": "iPhone 15 Pro",
      "platform": "ios",
      "verified_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```
