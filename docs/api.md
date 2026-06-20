# Business API Developer Documentation

## Overview

This document describes how to **create API keys** (both Business API Keys and Platform Integration Keys) from the central application `business.hamro.com` and how to use those keys to manage **channels, groups, members, and send messages**.

The system enforces that **API key creation** can only be performed from the **central host** (configured via `config/central_host.php`). All other actions are performed through the regular API (`/business-api/*`) using the `business.api` middleware.

---

## 1. Configuration

- **Central host**: `config/central_host.php`
  ```php
  return [
      // Allowed host for key creation (default: business.hamro.com)
      'allowed_host' => env('CENTRAL_HOST', 'business.hamro.com'),
  ];
  ```
- **Middleware**: `App\Http\Middleware\EnsureCentralHost` validates the request host before allowing key creation routes.

---

## 2. Authentication

All API requests (except key creation) must include the header `X-Business-API-Key` with a **valid API key**.

```http
X-Business-API-Key: bsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

The `BusinessApiAuthenticate` middleware resolves the key, verifies it is active/valid and injects:
- `business_api_key` – the `BusinessApiKey` model instance
- `business` – the owning `Business` model (platform)

---

## 3. Creating API Keys (Central Host Only)

### 3.1 Business API Key (Own Business)

**Endpoint**: `POST /businesses/{business}/api-keys`

**Headers**:
- `Host: business.hamro.com`
- Auth (Sanctum) for the business owner

**Payload**:
```json
{
  "name": "My API Key",
  "service_name": "my_service",
  "scopes": ["messages:send", "groups:manage"],
  "expires_at": "2027-12-31T23:59:59Z"
}
```

**Response (201)**:
```json
{
  "id": "uuid",
  "key": "bsk_XXXXXXXXXXXXXXXX",
  "service_name": "my_service",
  "scopes": [...],
  "expires_at": "...",
  "key_type": "business"
}
```

### 3.2 Platform Integration Key (Delegated)

**Endpoint**: `POST /businesses/{business}/api-keys/delegated`

**Headers**:
- `Host: business.hamro.com`
- Auth (Sanctum) for the **company** business that will delegate the key.

**Payload**:
```json
{
  "platform_business_id": "uuid-of-platform",
  "name": "Platform Key",
  "service_name": "platform_service",
  "scopes": ["messages:send", "groups:manage"],
  "platform_name": "SIMSNEPAL.com",
  "platform_website": "https://simsnepal.com"
}
```

The payload must reference a **platform business** that has an approved `BusinessPlatformCompany` relationship (`status = approved`, `can_send_messages = true`).

**Key Association**
Each API key created is bound to a `business_id`. The `key_type` indicates whether it is a Business API Key (`business`) or a Platform Integration Key (`platform`). This association is used to enforce permission checks and to tag the key's owning business.

**Response (201)**:
```json
{
  "message": "Delegated API key created successfully.",
  "api_key": { ... },
  "key": "bsk_XXXXXXXXXXXXXXXX"
}
```
---

## 4. Channel / Group Management (Platform Keys)

All group/channel actions are under the **business‑api** namespace and require a **platform integration key**.

### 4.1 Create a Group or Channel

**Endpoint**: `POST /business-api/groups`

**Headers**: `X-Business-API-Key: <platform_key>`

> **Note**: Both Business API Keys and Platform Integration Keys can call this endpoint. Business keys operate within their own business context, while Platform keys act on behalf of the business that issued the key (or a delegated business when using a Platform Integration Key).

**Payload**:
```json
{
  "name": "Support Channel",
  "description": "Customer support",
  "group_type": "channel"   // "group" for regular group
}
```

**Response (201)** returns the created `BusinessGroup` with its associated `thread_id`.

### 4.2 List Groups / Channels

`GET /business-api/groups`

Returns a paginated list of groups owned by the platform business.

### 4.3 Update Group

`PATCH /business-api/groups/{group}`

**Payload** (any of):
```json
{ "name": "New name", "description": "New description" }
```

### 4.4 Delete Group

`DELETE /business-api/groups/{group}`

---

## 5. Managing Members

### 5.1 Add Member to Group / Channel

**Endpoint**: `POST /business-api/groups/{group}/members`

**Payload** (choose one):
```json
{ "user_id": "uuid-of-user" }
```
or
```json
{ "external_client_id": "client‑123" }
```
If an `external_client_id` is supplied, the system resolves the corresponding `BusinessClient` to obtain the underlying `user_id`.

**Response (201)**: Member information.

### 5.2 List Members

`GET /business-api/groups/{group}/members`

Paginated list of members with their `user` relationship.

### 5.3 Remove Member

`DELETE /business-api/groups/{group}/members/{memberId}`

---

## 6. Sending Messages

### 6.1 Send Message to a Group / Channel

**Endpoint**: `POST /business-api/notifications`

**Payload**:
```json
{
  "group_id": "uuid-of-group",
  "message": "Hello, team!",
  "attachment": null
}
```

The controller (`BusinessNotificationController::sendNotification`) validates that:
- The API key has the `messages:send` scope.
- The platform is approved (`BusinessPlatformCompany`) to send messages on behalf of the target business.

**Response (200)**: Message details.

### 6.2 Direct Message to a Member

Use the same endpoint, providing `member_id` instead of `group_id`:
```json
{ "member_id": "uuid-of-member", "message": "Hi!" }
```

---

## 7. Error Handling & Status Codes

| Code | Situation |
|------|------------|
| **401** | Missing or invalid `X-Business-API-Key` header |
| **403** | API key inactive/expired, or host not allowed for key creation |
| **404** | Resource not found (group, member, business) |
| **422** | Validation error (e.g., missing `user_id`/`external_client_id`) |
| **200/201** | Successful operation |

All error responses include a JSON `{ "message": "…" }`.

---

## 8. Example cURL Requests

```bash
# Create a business API key (central host only)
curl -X POST https://business.hamro.com/businesses/{biz_id}/api-keys \
  -H "Host: business.hamro.com" \
  -H "Authorization: Bearer <sanctum-token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Key 1","service_name":"svc1","scopes":["messages:send","groups:manage"]}'

# Create a platform delegated key
curl -X POST https://business.hamro.com/businesses/{company_id}/api-keys/delegated \
  -H "Host: business.hamro.com" \
  -H "Authorization: Bearer <sanctum-token>" \
  -H "Content-Type: application/json" \
  -d '{"platform_business_id":"{platform_id}","name":"Plat Key","service_name":"plat_svc","scopes":["messages:send"],"platform_name":"SIMSNEPAL.com"}'

# Create a group using the platform key
curl -X POST https://api.chathamro.com/business-api/groups \
  -H "X-Business-API-Key: bsk_XXXXXXXXXXXXXXXX" \
  -H "Content-Type: application/json" \
  -d '{"name":"Support","group_type":"channel"}'

# Add a member by user id
curl -X POST https://api.chathamro.com/business-api/groups/{group_id}/members \
  -H "X-Business-API-Key: bsk_XXXXXXXXXXXXXXXX" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"{user_uuid}"}'

# Send a message to the group
curl -X POST https://api.chathamro.com/business-api/notifications \
  -H "X-Business-API-Key: bsk_XXXXXXXXXXXXXXXX" \
  -H "Content-Type: application/json" \
  -d '{"group_id":"{group_uuid}","message":"Hello everyone!"}'
```

---

## 9. Testing

The test suite includes `BusinessApiKeyCentralHostTest` to verify that key creation is blocked when the request host is not the configured central host.

Run all tests:
```bash
php artisan test
```

---

**That’s the complete developer guide for creating keys, managing channels/groups, adding members, and sending messages using Business and Platform API keys.**
