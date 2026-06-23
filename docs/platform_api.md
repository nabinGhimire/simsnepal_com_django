# Platform API Guide

## Overview
This document explains how a **platform** can interact with the chat‑Hamro service using its **Platform Key** and **Business Key**. You will learn how to:
- Authenticate API requests.
- Create channels and groups.
- Add users (admin and non‑admin) to channels/groups.
- Verify whether a user exists by **email** or **phone**.
- Perform common management actions.

All examples use `curl` with JSON payloads. Adjust the base URL (`https://api.chat-hamro.com/v1`) to match your deployment.

---

## 1. Authentication

The service uses **two API keys**:
1. **Platform Key** – identifies the originating platform (your application).
2. **Business Key** – identifies the business/tenant within the platform.

Both keys must be sent in the request headers:

```http
X-Platform-Key: YOUR_PLATFORM_KEY
X-Business-Key: YOUR_BUSINESS_KEY
```

> **Important**: Keep these keys secret. Do not embed them in client‑side code.

---

## 2. Create a Channel

**Endpoint**: `POST /channels`

**Request Body**:
```json
{
  "name": "string",          // Channel name, must be unique per business
  "description": "string",   // Optional description
  "type": "public|private"   // Visibility
}
```

**Example**:
```bash
curl -X POST "https://api.chat-hamro.com/v1/channels" \
  -H "Content-Type: application/json" \
  -H "X-Platform-Key: $PLATFORM_KEY" \
  -H "X-Business-Key: $BUSINESS_KEY" \
  -d '{"name":"math‑101","description":"Math class channel","type":"private"}'
```

**Response** (201 Created):
```json
{
  "id": "channel_abc123",
  "name": "math‑101",
  "type": "private"
}
```
---

## 3. Create a Group (e.g., Grade or Section)

**Endpoint**: `POST /groups`

**Request Body**:
```json
{
  "name": "string",          // Group name
  "channel_id": "string"      // ID of the channel the group belongs to
}
```

**Example**:
```bash
curl -X POST "https://api.chat-hamro.com/v1/groups" \
  -H "Content-Type: application/json" \
  -H "X-Platform-Key: $PLATFORM_KEY" \
  -H "X-Business-Key: $BUSINESS_KEY" \
  -d '{"name":"grade‑10","channel_id":"channel_abc123"}'
```

**Response** (201 Created):
```json
{
  "id": "group_xyz789",
  "name": "grade‑10",
  "channel_id": "channel_abc123"
}
```
---

## 4. Add Users to a Group or Channel

### 4.1 Add a **Non‑Admin** User

**Endpoint**: `POST /groups/{group_id}/users`

**Request Body**:
```json
{
  "email": "user@example.com",
  "phone": "+1234567890",
  "role": "member"   // "member" is the non‑admin role
}
```

**Example**:
```bash
curl -X POST "https://api.chat-hamro.com/v1/groups/group_xyz789/users" \
  -H "Content-Type: application/json" \
  -H "X-Platform-Key: $PLATFORM_KEY" \
  -H "X-Business-Key: $BUSINESS_KEY" \
  -d '{"email":"student1@example.com","phone":"+15551234567","role":"member"}'
```

### 4.2 Add an **Admin** User

Use the same endpoint but set `role` to `admin`.

```json
{
  "email": "teacher@example.com",
  "phone": "+15559876543",
  "role": "admin"
}
```

---

## 5. Verify User Existence

You can query the platform to see if a user already exists by **email** or **phone**.

**Endpoint**: `GET /users/lookup`

**Query Parameters** (choose **one**):
- `email=user@example.com`
- `phone=+1234567890`

**Example (email)**:
```bash
curl -G "https://api.chat-hamro.com/v1/users/lookup" \
  -H "X-Platform-Key: $PLATFORM_KEY" \
  -H "X-Business-Key: $BUSINESS_KEY" \
  --data-urlencode "email=parent@example.com"
```

**Response** (200 OK – user exists):
```json
{
  "exists": true,
  "user": {
    "id": "user_7f4c2",
    "email": "parent@example.com",
    "phone": "+15551230000",
    "role": "member"
  }
}
```

**Response** (200 OK – not found):
```json
{ "exists": false }
```
---

## 6. Additional Helpful Endpoints

| Action | Method | Endpoint | Description |
|--------|--------|----------|-------------|
| List Channels | `GET` | `/channels` | Retrieves all channels for the business |
| List Groups in a Channel | `GET` | `/channels/{channel_id}/groups` | Lists groups belonging to a channel |
| Remove User from Group | `DELETE` | `/groups/{group_id}/users/{user_id}` | Revokes membership |
| Update User Role | `PATCH` | `/groups/{group_id}/users/{user_id}` | Change `role` between `member` and `admin` |

---

## 7. Error Handling
All error responses follow the format:
```json
{
  "error": {
    "code": "string",   // e.g., "INVALID_KEY", "NOT_FOUND", "VALIDATION_ERROR"
    "message": "Human readable description"
  }
}
```
Typical HTTP status codes:
- **400** – Bad request / validation error.
- **401** – Authentication failed (invalid Platform/Business key).
- **404** – Resource not found (channel, group, or user).
- **409** – Conflict (e.g., channel name already exists).

---

## 8. Best Practices
- **Cache lookup results** for email/phone to reduce repeat calls.
- **Validate payloads** client‑side before sending to avoid 400 errors.
- **Use idempotent operations** when adding users; the API will return the existing user if already a member.
- **Rotate keys** periodically and store them securely (e.g., environment variables, secret manager).

---

## 9. Sample Workflow (Create Classroom)
1. **Create a channel** for the class.
2. **Create a group** representing the grade/section.
3. **Add teacher(s)** as `admin` role.
4. **Add students** as `member` role.
5. **Optionally verify** each student’s email/phone before adding.

---

## 10. Reference
- Full OpenAPI specification: `https://api.chat-hamro.com/v1/openapi.yaml`
- Authentication guide: `https://docs.chat-hamro.com/authentication`
- Rate limits: 1000 requests per minute per business key.

---

*Document generated on 2026‑06‑20.*
