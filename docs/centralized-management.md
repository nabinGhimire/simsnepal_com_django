# Centralized Business Management

This document describes how `hamro.com` (core identity + chat engine) and `business.hamro.com` (business management portal) work together.

## Roles in the system

- **System (Hamro)**: Owns identity, messaging threads, and all core APIs.
- **Business**: Sends messages directly to users from its own profile.
- **Platform**: Can send on behalf of a business after approval (example: Amazon sending for Apple).

## Domain model

- `users`: Registered once in Hamro and reused everywhere.
- `businesses`: Company/platform entities managed from `business.hamro.com`.
- `business_api_keys`: API credentials for direct messaging and delegated platform messaging.
- `business_platform_companies`: Approval records between platform and business.
- `business_clients`: Links external platform identifiers to Hamro users.

## Management flows

### 0) Create a platform (in Hamro core)

Platforms are stored in the same `businesses` table as companies, with `type: "platform"`.

Create/sync a platform by calling the same system sync endpoint:

- `POST /api/v1/system/businesses/sync`
- Header: `X-System-API-Key: {SYSTEM_API_KEY}`

Minimal example payload:

```json
{
  "user_id": "owner-uuid",
  "name": "My Platform",
  "type": "platform",
  "is_active": true
}
```

### 1) Sync business into Hamro core

`business.hamro.com` should call:

- `POST /api/v1/system/businesses/sync`
- Header: `X-System-API-Key: {SYSTEM_API_KEY}`

This creates/updates the business and ensures a default API key exists.

Example payload (nullable fields allowed):

```json
{
  "user_id": "owner-uuid",
  "name": "Acme Corp",
  "type": "company",
  "website": "https://acme.com",
  "contact_email": "contact@acme.com",
  "contact_phone": "+9779800000000",
  "contact_name": "Acme Support",
  "address": "Kathmandu, Nepal",
  "metadata": { "notes": "optional" },
  "is_active": true
}
```

### 2) Business direct messaging

Business uses its own API key on:

- `POST /api/v1/business-api/notifications`
- Header: `X-Business-API-Key: bsk_...`

Supported content now includes:

- text (`message`)
- image upload (`image`)
- document/file upload (`document`)

### 3) Platform messaging on behalf of business

Two supported models:

- **Authorization model**:
  1. Platform requests authorization.
  2. Company approves/rejects.
  3. Platform key can be delegated for on-behalf messaging.
- **Delegated key model**:
  - Company creates delegated key for an approved platform.
  - The key is owned by the platform and tagged with `on_behalf_of_business_id`.

Delegated key endpoints:

- `GET /api/v1/businesses/{business}/api-keys/delegated`
- `POST /api/v1/businesses/{business}/api-keys/delegated`

### 4) Business owner API key management (portal)

API keys are created/rotated by the **system app** (`business.hamro.com`) using `X-System-API-Key`.

- `GET /api/v1/system/businesses/{business}/api-keys` (list)
- `POST /api/v1/system/businesses/{business}/api-keys` (create)
- `POST /api/v1/system/businesses/{business}/api-keys/{apiKey}/regenerate` (rotate key)

Delegated keys (platform on behalf of business):
- `GET /api/v1/system/businesses/{business}/api-keys/delegated`
- `POST /api/v1/system/businesses/{business}/api-keys/delegated`

## Platform-managed groups/channels

After a company approves a platform with `can_manage_groups=true`, the platform uses the delegated key (`X-Business-API-Key`) to manage channels/groups for the business:

- `POST /api/v1/business-api/groups` (create group/channel)
- `POST /api/v1/business-api/groups/{group}/members` (add member by `user_id` or `external_client_id`)

## Security boundaries

- `system.api` middleware protects internal system sync endpoints.
- `business.api` middleware validates `X-Business-API-Key`.
- Owner-only business management actions are policy-protected.
- Delegated keys require an approved `business_platform_companies` relation with `can_send_messages=true`.
