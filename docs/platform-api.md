# Hamro Chat — Platform Integration API

> Base URL: `https://your-domain.com/api/v1`
> All request bodies are JSON unless noted. All responses are JSON.

---

## Authentication

There are two separate auth mechanisms depending on which API surface you are calling.

### System API (internal management portal only)

Used for provisioning businesses and API keys. Never expose this key to client apps.

```
X-System-API-Key: <system_key_from_env>
```

The key is set in your `.env` as `SYSTEM_API_KEY`.

### Business / Platform API

Used for all runtime operations (creating threads, syncing members, sending messages).

```
X-Business-Key: <your_api_key>
```

The key value starts with `hamro_` followed by the platform slug and a random string,
e.g. `hamro_simsnepal_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.

---

## Concepts

| Term | Meaning |
|---|---|
| **Platform** | The external app integrating with Hamro (e.g. simsnepal). Registered as `type=platform`. |
| **Company / Business** | The school, organisation, or business that the platform manages on behalf of. `type=company`. |
| **Delegated key** | An API key owned by the **platform** but scoped to act on behalf of a specific **company**. This is the key simsnepal uses. |
| **Thread** | A chat conversation — either a `group` (two-way) or `channel` (one-way broadcast). |
| **BusinessGroup** | The record that links a Thread to a Business. Required for scoping. |

---

## Setup Flow (one-time, done via System API or management portal)

```
1. Register the platform business        POST /system/businesses/sync  (type=platform)
2. Register the company business         POST /system/businesses/sync  (type=company)
3. Create a delegated API key            POST /system/businesses/{company_id}/api-keys/delegated
4. Use that key for all runtime calls    X-Business-Key: hamro_simsnepal_xxx...
```

---

## 1. System API

> Requires header: `X-System-API-Key: <system_key>`
> Prefix: `/api/v1/system`

---

### 1.1 Sync / Register a Business

Creates the business if it doesn't exist, or updates it if it does.
Calling this repeatedly with the same `(user_id, name, type)` is safe — it is idempotent.
Also auto-provisions a default API key if one does not yet exist.

```
POST /system/businesses/sync
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | uuid | no | Provide to update a specific record by ID |
| `user_id` | uuid | yes | The Hamro user who owns this business |
| `name` | string | yes | max 255 |
| `type` | string | yes | `platform`, `company`, or `individual` |
| `is_active` | boolean | no | default true |
| `is_verified` | boolean | no | default false |
| `website` | url | no | |
| `contact_email` | email | no | |
| `contact_phone` | string | no | |
| `contact_name` | string | no | |
| `address` | string | no | max 2000 |
| `metadata` | object | no | arbitrary key-value |

**Example — register the platform**

```json
{
  "user_id": "a1acdbb0-aea0-423b-8313-a20415a93661",
  "name": "SIMS Nepal",
  "type": "platform",
  "is_active": true
}
```

**Example — register a company (school)**

```json
{
  "user_id": "a1bd3ad2-bf71-4732-961a-8525f22c18a1",
  "name": "Samata School",
  "type": "company",
  "is_active": true
}
```

**Response `200`**

```json
{
  "message": "Business synced successfully",
  "business": {
    "id": "a1d6aed5-cd28-4e3c-832c-104b4683b304",
    "user_id": "a1bd3ad2-bf71-4732-961a-8525f22c18a1",
    "name": "Samata School",
    "type": "company",
    "is_active": true,
    "is_verified": false,
    "created_at": "2026-05-22T07:18:03.000000Z",
    "updated_at": "2026-05-22T07:18:03.000000Z"
  },
  "api_key": "hamro_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

---

### 1.2 List Businesses

```
GET /system/businesses
```

Returns a paginated list of all businesses. Standard Laravel pagination envelope.

---

### 1.3 Delete a Business

```
DELETE /system/businesses/{business_id}
```

**Response `200`**

```json
{ "message": "Business deleted" }
```

---

### 1.4 List API Keys for a Business

```
GET /system/businesses/{business_id}/api-keys
```

Returns only the business's own (non-delegated) keys.

---

### 1.5 Create an API Key

```
POST /system/businesses/{business_id}/api-keys
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes* | *required if `service_name` absent |
| `service_name` | string | yes* | *required if `name` absent. Normalized to lowercase alphanumeric. |
| `scopes` | array | no | e.g. `["messages:send"]` |
| `expires_at` | datetime | no | ISO 8601 |
| `is_active` | boolean | no | default true |

**Response `201`**

```json
{
  "message": "API key created successfully.",
  "api_key": { "id": "...", "name": "...", "key_type": "personal", ... },
  "key": "hamro_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

---

### 1.6 Create a Delegated (Platform) API Key

This is the key the platform uses to act on behalf of a company.
Also automatically creates/approves the `BusinessPlatformCompany` authorization record.

```
POST /system/businesses/{company_business_id}/api-keys/delegated
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `platform_business_id` | uuid | yes | ID of the platform business (simsnepal) |
| `name` | string | yes* | *required if `service_name` absent |
| `service_name` | string | yes* | *required if `name` absent |
| `scopes` | array | no | Auto-appends `messages:send` and `groups:manage` |
| `expires_at` | datetime | no | |

**Example**

```json
{
  "platform_business_id": "a20d2190-b026-4ae3-ae16-b96c519aa2e4",
  "name": "SIMS Nepal — Samata School",
  "service_name": "simsnepal_samata"
}
```

**Response `201`**

```json
{
  "message": "Delegated API key created successfully.",
  "api_key": {
    "id": "...",
    "business_id": "a20d2190-b026-4ae3-ae16-b96c519aa2e4",
    "on_behalf_of_business_id": "a1d6aed5-cd28-4e3c-832c-104b4683b304",
    "key_type": "platform",
    "scopes": ["messages:send", "groups:manage"],
    "is_active": true
  },
  "key": "hamro_simsnepal_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

Store this key securely. It is the value you send in `X-Business-Key` for all runtime calls.

---

### 1.7 Regenerate an API Key

```
POST /system/businesses/{business_id}/api-keys/{api_key_id}/regenerate
```

**Response `200`**

```json
{
  "message": "API key regenerated successfully.",
  "api_key": { ... },
  "key": "hamro_simsnepal_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
}
```

---

### 1.8 Update an API Key

```
PATCH /system/businesses/{business_id}/api-keys/{api_key_id}
```

| Field | Type | Notes |
|---|---|---|
| `name` | string | |
| `service_name` | string | |
| `scopes` | array | |
| `expires_at` | datetime | |
| `is_active` | boolean | Set `false` to revoke |

---

### 1.9 Delete an API Key

```
DELETE /system/businesses/{business_id}/api-keys/{api_key_id}
```

Response `204` — no body.

---

## 2. Platform API — Threads

> Requires header: `X-Business-Key: <delegated_platform_key>`
> Prefix: `/api/v1/platform`
> Every thread endpoint is scoped to the company that the key was issued for.
> A platform cannot read or modify threads belonging to a different company.

---

### 2.1 List Threads

Returns only threads created by this platform for the authenticated company.

```
GET /platform/threads
```

**Response `200`**

```json
[
  {
    "id": "thread-uuid",
    "type": 2,
    "subject": "Class 5A — Notice Board",
    "is_channel": true,
    "messaging": true,
    "name": "Class 5A — Notice Board",
    "created_at": "2026-06-01T09:00:00.000000Z"
  }
]
```

---

### 2.2 Create a Thread

```
POST /platform/threads
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | string | yes | `group` or `channel` |
| `name` | string | yes | Required for group and channel |
| `description` | string | no | |

- `channel` — one-way broadcast, members cannot send messages
- `group` — two-way chat, members can send messages

**Example**

```json
{
  "type": "channel",
  "name": "Class 5A — Notice Board",
  "description": "Official notices for Class 5A parents"
}
```

**Response `201`**

```json
{
  "id": "d1e2f3a4-...",
  "type": 2,
  "subject": "Class 5A — Notice Board",
  "is_channel": true,
  "messaging": true,
  "name": "Class 5A — Notice Board",
  "created_at": "2026-07-12T10:00:00.000000Z"
}
```

The business owner is automatically added as an admin participant.
Save the returned `id` — you need it for all subsequent calls on this thread.

---

### 2.3 Get a Thread

```
GET /platform/threads/{thread_id}
```

**Response `200`** — same shape as create response.

---

### 2.4 Update a Thread

```
PUT /platform/threads/{thread_id}
```

**Request**

| Field | Type | Notes |
|---|---|---|
| `name` | string | Updates the thread subject |
| `description` | string | nullable |

**Response `200`** — updated thread object.

---

### 2.5 Delete a Thread

```
DELETE /platform/threads/{thread_id}
```

**Response `204`** — no body.

---

## 3. Platform API — Members

---

### 3.1 List Members

```
GET /platform/threads/{thread_id}/users
```

**Response `200`**

```json
[
  {
    "participant_id": "...",
    "user_id": "a1bd3ad2-...",
    "admin": true,
    "email": "owner@school.edu.np",
    "phone": "9800000001",
    "created_at": "2026-07-12T10:00:00.000000Z"
  },
  {
    "participant_id": "...",
    "user_id": "a1adf911-...",
    "admin": false,
    "email": "parent@example.com",
    "phone": "9800000002",
    "created_at": "2026-07-12T10:01:00.000000Z"
  }
]
```

---

### 3.2 Add a Single Member

```
POST /platform/threads/{thread_id}/users
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `user_id` | uuid | yes | Must be an existing Hamro user |

**Example**

```json
{ "user_id": "a1adf911-0f27-43bf-b1fa-c36b0fdd74c2" }
```

**Response `200`**

```json
{ "message": "User added to thread" }
```

Returns `200` (not `409`) if already a member.

---

### 3.3 Add Members in Batch

Use this for sync operations. Existing members are skipped, not errored.

```
POST /platform/threads/{thread_id}/users/batch
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `user_ids` | array of uuid | yes | All must be existing Hamro users |

**Example**

```json
{
  "user_ids": [
    "a1adf911-0f27-43bf-b1fa-c36b0fdd74c2",
    "a1acbfb0-ad18-4845-b1f8-ecb5b97c8c11",
    "a1d93fd9-fb63-4c19-b5af-0c511280efa1"
  ]
}
```

**Response `200`**

```json
{
  "added": [
    "a1acbfb0-ad18-4845-b1f8-ecb5b97c8c11",
    "a1d93fd9-fb63-4c19-b5af-0c511280efa1"
  ],
  "existing": [
    "a1adf911-0f27-43bf-b1fa-c36b0fdd74c2"
  ],
  "invalid": []
}
```

---

### 3.4 Remove a Member

The business owner cannot be removed. Returns `403` if attempted.

```
DELETE /platform/threads/{thread_id}/users
```

**Request**

| Field | Type | Required |
|---|---|---|
| `user_id` | uuid | yes |

**Example**

```json
{ "user_id": "a1acbfb0-ad18-4845-b1f8-ecb5b97c8c11" }
```

**Response `200`**

```json
{ "message": "User removed from thread" }
```

---

## 4. Platform API — Roles

The business owner's admin role is protected and cannot be changed by the platform.

---

### 4.1 Update a Single User's Role

```
PATCH /platform/threads/{thread_id}/users/{user_id}/role
```

**Request**

| Field | Type | Required | Values |
|---|---|---|---|
| `role` | string | yes | `admin` or `member` |

**Example**

```json
{ "role": "admin" }
```

**Response `200`**

```json
{
  "message": "User role updated to admin successfully",
  "participant_id": "...",
  "user_id": "a1acbfb0-...",
  "admin": true
}
```

---

### 4.2 Batch Update Roles (sync-friendly)

Designed for member sync calls. The business owner is silently skipped if included in `member`.
IDs can appear in `admin` or `member` but not both.

```
PATCH /platform/threads/{thread_id}/users/role/batch
```

**Request**

| Field | Type | Notes |
|---|---|---|
| `admin` | array of uuid | Users to promote to admin |
| `member` | array of uuid | Users to demote to member |

At least one of `admin` or `member` is required.

**Example**

```json
{
  "admin": ["a1adf911-0f27-43bf-b1fa-c36b0fdd74c2"],
  "member": [
    "a1acbfb0-ad18-4845-b1f8-ecb5b97c8c11",
    "a1d93fd9-fb63-4c19-b5af-0c511280efa1"
  ]
}
```

**Response `200`**

```json
{
  "updated": ["a1adf911-...", "a1acbfb0-..."],
  "unchanged": ["a1d93fd9-..."],
  "not_found": []
}
```

---

## 5. Platform API — Messages

---

### 5.1 Send a Message

```
POST /platform/threads/{thread_id}/messages
```

**Request**

| Field | Type | Required | Notes |
|---|---|---|---|
| `body` | string | yes | Message text |
| `type` | string | no | `text` (default), `image`, `document`, `audio`, `video` |
| `user_id` | uuid | no | Send as a specific user. Omit to send as the business. |

**Example — school notice sent as the business**

```json
{
  "body": "School will be closed on Thursday due to public holiday.",
  "type": "text"
}
```

**Example — message attributed to a specific teacher**

```json
{
  "body": "Homework submitted. Well done!",
  "type": "text",
  "user_id": "a1bd3ad2-bf71-4732-961a-8525f22c18a1"
}
```

**Response `201`** — full message object including `id`, `body`, `type`, `owner`, `created_at`.

---

## 6. Platform API — Thread Avatar

---

### 6.1 Upload Avatar

```
POST /platform/threads/{thread_id}/avatar
Content-Type: multipart/form-data
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `image` | file | yes | Image file, max 5 MB |

**Response `200`** — updated thread object.

---

### 6.2 Remove Avatar

```
DELETE /platform/threads/{thread_id}/avatar
```

**Response `200`** — updated thread object.

---

## 7. Platform API — User Lookup

Use these before adding members to resolve Hamro user IDs from phone/email.

---

### 7.1 Lookup Single User

```
GET /platform/users/lookup?email=user@example.com
GET /platform/users/lookup?phone=9800000001
```

**Response — user found `200`**

```json
{
  "exists": true,
  "user": {
    "id": "a1adf911-0f27-43bf-b1fa-c36b0fdd74c2",
    "email": "user@example.com",
    "phone": "9800000001",
    "first_name": "Ram",
    "last_name": "Thapa",
    "username": "ramthapa"
  }
}
```

**Response — not found `200`**

```json
{ "exists": false }
```

---

### 7.2 Batch Lookup

```
POST /platform/users/lookup/batch
```

**Request**

| Field | Type | Notes |
|---|---|---|
| `emails` | array of string | Required if `phones` absent |
| `phones` | array of string | Required if `emails` absent |

**Example**

```json
{
  "phones": ["9800000001", "9800000002", "9800000003"]
}
```

**Response `200`**

```json
{
  "users": [
    {
      "id": "a1adf911-...",
      "email": "user1@example.com",
      "phone": "9800000001",
      "first_name": "Ram",
      "last_name": "Thapa",
      "username": "ramthapa"
    },
    {
      "id": "a1acbfb0-...",
      "email": "user2@example.com",
      "phone": "9800000002",
      "first_name": "Sita",
      "last_name": "Sharma",
      "username": "sitasharma"
    }
  ],
  "not_found": {
    "emails": [],
    "phones": ["9800000003"]
  }
}
```

---

## 8. Business-API — Groups (alternative surface)

This is a higher-level alternative to the Platform API. It uses `BusinessGroup` records
as the primary object and manages both the group metadata and thread participants together.

> Requires header: `X-Business-Key: <delegated_platform_key>`
> Prefix: `/api/v1/business-api`
> The key **must** be a delegated platform key (`key_type=platform`) with `groups:manage` scope.

---

### 8.1 List Groups

```
GET /business-api/groups
```

Returns paginated `BusinessGroup` records for the authenticated company.

---

### 8.2 Create a Group

```
POST /business-api/groups
```

**Request**

| Field | Type | Required | Values |
|---|---|---|---|
| `name` | string | yes | max 255 |
| `description` | string | no | |
| `group_type` | string | yes | `group` or `channel` |

**Example**

```json
{
  "name": "Class 10 Parents",
  "description": "Group for Class 10 parent communication",
  "group_type": "group"
}
```

**Response `201`**

```json
{
  "id": "bg-uuid",
  "business_id": "a1d6aed5-...",
  "name": "Class 10 Parents",
  "group_type": "group",
  "thread_id": "thread-uuid",
  "created_at": "2026-07-12T10:00:00.000000Z"
}
```

Both the `BusinessGroup` record and the underlying `Thread` are created in one call.
The business owner is automatically added as an admin participant on the thread.

---

### 8.3 Get a Group

```
GET /business-api/groups/{group_id}
```

Returns the group with its members.

---

### 8.4 Update a Group

```
PATCH /business-api/groups/{group_id}
```

| Field | Type |
|---|---|
| `name` | string |
| `description` | string / null |

---

### 8.5 Delete a Group

```
DELETE /business-api/groups/{group_id}
```

Response `204` — no body.

---

### 8.6 List Members

```
GET /business-api/groups/{group_id}/members
```

Returns paginated members with their linked Hamro user data.

---

### 8.7 Add a Member

Supports adding by Hamro `user_id` or by your own `external_client_id` (if you have
previously registered the client via `BusinessClient`).

```
POST /business-api/groups/{group_id}/members
```

**Request**

| Field | Type | Notes |
|---|---|---|
| `user_id` | uuid | Hamro user ID — use lookup endpoints to resolve |
| `external_client_id` | string | Your own system's user/client identifier |

At least one of the two is required.

**Example — by Hamro user ID**

```json
{ "user_id": "a1adf911-0f27-43bf-b1fa-c36b0fdd74c2" }
```

**Example — by your own client ID**

```json
{ "external_client_id": "SIMS_STUDENT_4829" }
```

**Response `201`** — member record.
Returns `409` if already a member.

---

### 8.8 Remove a Member

The business owner cannot be removed. Returns `403` if attempted.

```
DELETE /business-api/groups/{group_id}/members/{member_id}
```

Response `204` — no body.

---

### 8.9 Update Member Role

```
PATCH /business-api/groups/{group_id}/members/{member_id}/role
```

**Request**

| Field | Type | Values |
|---|---|---|
| `role` | string | `admin` or `member` |

**Response `200`**

```json
{
  "message": "Member role updated to admin successfully",
  "member_id": "...",
  "user_id": "...",
  "admin": true
}
```

---

## 9. Error Responses

| Status | Meaning |
|---|---|
| `401` | Missing or invalid `X-Business-Key` / `X-System-API-Key` |
| `403` | Key exists but lacks permission, platform not approved, or trying to remove/demote the business owner |
| `404` | Thread or resource not found, or the thread does not belong to your business |
| `409` | Member already exists in group |
| `422` | Validation error — response includes `errors` object |

**Validation error shape**

```json
{
  "errors": {
    "type": ["The type field is required."],
    "name": ["The name field is required when type is group."]
  }
}
```

---

## 10. Recommended Integration Flow for simsnepal

```
Setup (one-time per school):
  1. POST /system/businesses/sync          → get company business_id
  2. POST /system/businesses/{id}/api-keys/delegated  → get delegated key
  3. Store: { company_id, thread_id, delegated_key } per school in your DB

On school year / class setup:
  4. POST /platform/threads                → create one thread per class
     or
     POST /business-api/groups            → same, with richer metadata

On student/parent roster sync:
  5. POST /platform/users/lookup/batch    → resolve phone numbers → user_ids
  6. POST /platform/threads/{id}/users/batch  → add resolved user_ids
  7. PATCH /platform/threads/{id}/users/role/batch  → set roles
     (business owner is always protected, safe to include in member list)

On roster change (student leaves/joins):
  8. POST  /platform/threads/{id}/users   → add new member
  9. DELETE /platform/threads/{id}/users  → remove departed member

On sending a notice:
  10. POST /platform/threads/{id}/messages → send as business or as specific teacher
```

---

## 11. Key Rules to Remember

1. **Always persist the `thread_id`** returned from thread creation. There is no search-by-name endpoint.
2. **Always persist the `business_id`** returned from `businesses/sync`. Pass `id` on subsequent calls to avoid creating duplicate business records.
3. **Business owner is protected** — you can safely include the owner's `user_id` in remove or demote calls without risk; the API will silently skip them.
4. **One key per company** — each delegated key is scoped to a single company. If you manage multiple schools, create one delegated key per school.
5. **Thread scoping is strict** — a key for school A cannot access threads created for school B, even if both schools use simsnepal. Attempts return `404`.
