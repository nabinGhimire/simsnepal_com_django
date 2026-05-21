**Channels API**

Overview

Channels are a specialized kind of group thread used for announcements or one-to-many messaging. Internally they are `threads` with `type = GROUP` and `is_channel = true`. Most group behaviors apply but participant permissions are stricter by default.

Authentication

- All endpoints require `Authorization: Bearer <token>` (use the auth/verify-otp login flow to obtain a token).

Endpoints

- List Channels
  - Method: GET
  - URL: `/api/v1/channels`
  - Description: Returns recent channels for the authenticated provider. Response is a `GroupThreadCollection` with threads limited by `Messenger::getThreadsIndexCount()`.

- Create Channel
  - Method: POST
  - URL: `/api/v1/channels`
  - Body (JSON):

```json
{
  "subject": "Announcements",
  "providers": [{ "alias": "user", "id": "USER_ID" }],
  "is_channel": true
}
```

  - Notes: The `ChannelController` forces `is_channel = true` before delegating to `StoreGroupThread`. You can include `providers` to seed participants.

- Channel Page (infinite scroll)
  - Method: GET
  - URL: `/api/v1/channels/page/{channel}`
  - Description: Returns the next page of channels updated before the provided `{channel}` (uses same pagination semantics as groups page).

- Promote participant
  - Method: POST
  - URL: `/api/v1/channels/{channel}/promote`
  - Body options (JSON):

Promote existing participant by id:

```json
{ "participant_id": "PARTICIPANT_UUID" }
```

Create (or restore) and promote a provider via alias/id:

```json
{ "provider": { "alias": "user", "id": "USER_ID" } }
```

  - Notes: This action is authorized by `ParticipantPolicy::promote` when promoting an existing participant or by `create` when adding a new participant.

- Demote participant
  - Method: POST
  - URL: `/api/v1/channels/{channel}/demote`
  - Body (JSON):

```json
{ "participant_id": "PARTICIPANT_UUID" }
```

  - Notes: Demotion is authorized by `ParticipantPolicy::demote`.

Behavior

- Default channel participant permissions are `Participant::ChannelPermissions` (read-only). Promoted admins get `Participant::AdminPermissions` which include posting rights.
- Use `GET /api/v1/channels` for the latest channels and `GET /api/v1/channels/page/{channel}` to fetch older pages (infinite scroll).

Developer tips

- For UI: request `GET /api/v1/channels` (fetch 10–15 latest). On scroll call `/channels/page/{lastChannelId}`.
- For promoting by provider, pass `{ "provider": { "alias": "user", "id": "..." } }` — alias must match provider registry (usually `user`).
- Add caching at the edge or a short Redis cache for the channel index if traffic is high.
