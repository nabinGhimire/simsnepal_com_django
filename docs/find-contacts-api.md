# Find Contacts API Documentation

**Version:** 1.0.0
**Last Updated:** 2025

---

## Overview

The Find Contacts API allows mobile clients to efficiently discover registered users from their contact list. Instead of making hundreds of individual requests, clients send a batch of contacts (phone numbers, emails) and receive matched user profiles in a single optimized request.

### Key Features
- Batch search up to 100 contacts per request
- Supports both phone numbers and email addresses
- Phone number normalization (E164 format)
- Duplicate detection (same user matched by multiple contacts)
- Rate limited: 10 requests per minute per user
- Cached results for 5 minutes

---

## API Endpoint

```
POST /api/v1/contacts/find
```

### Headers

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer {token}` | Yes |
| `Content-Type` | `application/json` | Yes |
| `Accept` | `application/json` | Yes |

---

## Request

### Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `contacts` | `array<string>` | Yes | Array of contact identifiers (phone numbers, emails). Max 100 items. |

### Example Request

```json
POST /api/v1/contacts/find
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "contacts": [
    "+9779841234567",
    "user@example.com",
    "+9779812345678",
    "another@example.com"
  ]
}
```

### Phone Number Formats Supported

| Format | Example | Notes |
|--------|---------|-------|
| With country code | `+9779841234567` | Recommended |
| Without country code | `9841234567` | Auto-normalized to E164 |
| With spaces/dashes | `984-123-4567` | Auto-cleaned |
| International | `+1-555-123-4567` | Auto-cleaned |

---

## Response

### Success Response (200 OK)

```json
{
  "data": [
    {
      "contact": "+9779841234567",
      "found": true,
      "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "John Doe",
        "email": "john@example.com",
        "mobile_number": "+9779841234567",
        "username": "johndoe",
        "avatar_url": "https://hamro.com/storage/avatars/user.jpg",
        "type": "user"
      },
      "duplicate": null
    },
    {
      "contact": "user@example.com",
      "found": true,
      "user": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Jane Smith",
        "email": "user@example.com",
        "mobile_number": "+9779887654321",
        "username": "janesmith",
        "avatar_url": "https://hamro.com/storage/avatars/user.jpg",
        "type": "user"
      },
      "duplicate": null
    },
    {
      "contact": "+9779812345678",
      "found": false,
      "user": null,
      "duplicate": null
    }
  ],
  "meta": {
    "total_requested": 4,
    "total_found": 2
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `contact` | string | Original contact identifier from request |
| `found` | boolean | `true` if a registered user was matched |
| `user` | object\|null | User profile if found, null otherwise |
| `user.id` | string | Unique user identifier (UUID) |
| `user.name` | string | User's display name |
| `user.email` | string | User's email address |
| `user.mobile_number` | string | User's phone number |
| `user.username` | string | User's username |
| `user.avatar_url` | string | URL to user's profile picture |
| `user.type` | string | Always "user" |
| `duplicate` | string\|null | If same user matched by multiple contacts, this shows the primary contact |
| `meta.total_requested` | integer | Total contacts sent in request |
| `meta.total_found` | integer | Number of unique users found |

---

## Error Responses

### 422 Validation Error

```json
{
  "message": "The contacts field must have at most 100 items.",
  "errors": {
    "contacts": ["Maximum of 100 contacts allowed per request."]
  }
}
```

### 401 Unauthorized

```json
{
  "message": "Unauthenticated."
}
```

### 429 Too Many Requests

```json
{
  "message": "Too Many Attempts."
}
```

## User Contacts Sync - Overview

The user contacts feature allows you to:
1. **Store device contacts** - Save contacts from user's phone with device tracking
2. **Track registrations** - Know when contacts join Hamro
3. **Send notifications** - Notify users when their contacts join (one-time only)
4. **Handle sync scenarios** - New phone, deleted contacts, incremental updates

### How It Works

1. User logs in on Device A → Full sync contacts (Device A tracked)
2. User logs in on Device B → Full sync contacts (Device A + B tracked)
3. User adds contact on Device A → Incremental sync (add Device A to contact)
4. User deletes contact from Device A only → Contact still exists from Device B
5. Contact joins Hamro → Observer triggers → User gets push notification
6. Contact deleted from ALL devices → Contact soft deleted (no more notifications)

### Key Behaviors

| Scenario | Behavior |
|----------|----------|
| Contact synced from multiple devices | Track all devices, delete when ALL remove |
| Contact joined once | One-time notification only |
| Re-add after delete | No re-notification (already joined) |
| New phone login | Add new device, don't lose contacts from old phone |

### Sync Strategies

| Scenario | Endpoint | When to Use |
|----------|-----------|-------------|
| New device login | `POST /contacts/full-sync` | First time on new device |
| Add contact on phone | `POST /contacts/incremental-sync` | After adding on phone |
| Delete contact on phone | `POST /contacts/incremental-sync` | After deleting from phone |
| Background sync | `POST /contacts/store` | Daily periodic sync |
| Check new registrations | `POST /contacts/sync` | On app open |

---

## User Contacts Sync API

Store and sync device contacts to get notified when contacts join Hamro.

### Store Contacts (Incremental)

```
POST /api/v1/contacts/store
```

Add new contacts from a device. Tracks which device added each contact.

```json
{
  "device_id": "device-uuid-123",
  "contacts": [
    {"value": "+9779841234567", "label": "mobile", "display_name": "John Doe"},
    {"value": "user@example.com", "label": "home", "display_name": "User Name"}
  ]
}
```

**Response:**
```json
{
  "message": "Contacts stored successfully.",
  "data": {
    "stored": 2,
    "new_registrations": 1,
    "pending_notifications": 1
  }
}
```

### Full Sync (New Device)

```
POST /api/v1/contacts/full-sync
```

Sync all contacts from current device. Adds device to contacts, removes device from deleted contacts, soft deletes contacts with no remaining devices.

```json
{
  "device_id": "device-uuid-123",
  "contacts": [
    {"value": "+9779841234567", "label": "mobile", "display_name": "John Doe"},
    {"value": "user@example.com", "label": "home", "display_name": "User Name"}
  ]
}
```

**Response:**
```json
{
  "message": "Full sync completed.",
  "data": {
    "total_contacts": 50,
    "stored": 5,
    "updated": 45,
    "soft_deleted": 3,
    "new_registrations": 1,
    "pending_notifications": 2
  }
}
```

### Incremental Sync (Changes Only)

```
POST /api/v1/contacts/incremental-sync
```

Sync only added/removed contacts from a specific device. Most efficient for ongoing sync.

```json
{
  "device_id": "device-uuid-123",
  "added": [
    {"value": "+9779841234567", "display_name": "John Doe"}
  ],
  "removed": ["+9779887654321"]
}
```

**Response:**
```json
{
  "message": "Incremental sync completed.",
  "data": {
    "added": 1,
    "removed": 1,
    "new_registrations": 0,
    "pending_notifications": 2
  }
}
```

### Sync Registration Status

```
POST /api/v1/contacts/sync
```

Check if any stored contacts are now registered users (without adding/removing contacts).

```json
{}
```

### Get Registered Contacts

```
GET /api/v1/contacts/registered
```

Get list of contacts who are registered on Hamro.

**Response:**
```json
{
  "data": [
    {
      "contact_value": "+9779841234567",
      "contact_type": "phone",
      "display_name": "John Doe",
      "notified": true,
      "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "John Doe",
        "email": "john@example.com",
        "mobile_number": "+9779841234567",
        "avatar_url": "https://hamro.com/storage/avatars/user.jpg"
      },
      "registered_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Mark as Notified

```
POST /api/v1/contacts/notify
```

Mark contacts as notified (after showing in-app notification to user).

```json
{
  "contact_ids": [1, 2, 3]
}
```
POST /api/v1/contacts/store
```

Add new contacts only (does not remove deleted ones).

```json
{
  "contacts": [
    {"value": "+9779841234567", "label": "mobile", "display_name": "John Doe"},
    {"value": "user@example.com", "label": "home", "display_name": "User Name"}
  ]
}
```

### Full Sync (New Phone/Login)

```
POST /api/v1/contacts/full-sync
```

Replace all contacts. Use when user logs in from new device.

```json
{
  "contacts": [
    {"value": "+9779841234567", "label": "mobile", "display_name": "John Doe"},
    {"value": "user@example.com", "label": "home", "display_name": "User Name"}
  ]
}
```

Response:
```json
{
  "message": "Full sync completed.",
  "data": {
    "total_contacts": 50,
    "stored": 5,
    "removed": 3,
    "new_registrations": 1,
    "pending_notifications": 2
  }
}
```

### Incremental Sync (Changes Only)

```
POST /api/v1/contacts/incremental-sync
```

Sync only added/removed contacts. Most efficient for ongoing sync.

```json
{
  "added": [
    {"value": "+9779841234567", "display_name": "John Doe"}
  ],
  "removed": ["+9779887654321"]
}
```

### Sync Registration Status

```
POST /api/v1/contacts/sync
```

Check if any stored contacts are now registered users.

```json
{
  "contacts": []
}
```

### Get Registered Contacts

```
GET /api/v1/contacts/registered
```

Get list of contacts who are registered on Hamro.

### Mark as Notified

```
POST /api/v1/contacts/notify
```

Mark contacts as notified (after showing notification to user).

```json
{
  "contact_ids": [1, 2, 3]
}
```

---

## Integration: Contact Sync Strategy

### Scenario 1: New Phone Login

```dart
// User logs in on new device
Future<void> onNewDeviceLogin() async {
  // Get all contacts from new phone
  final deviceContacts = await getDeviceContacts();

  // Full sync - replaces all contacts
  final result = await api.fullSync(deviceContacts);

  // Check for new registrations
  if (result['pending_notifications'] > 0) {
    await showContactJoinedNotifications();
  }
}
```

### Scenario 2: Delete Contact on Phone

```dart
// User deleted contact from phone
Future<void> onContactDeleted(String deletedContact) async {
  // Incremental sync - just remove
  final result = await api.incrementalSync(
    added: [],
    removed: [deletedContact],
  );
}
```

### Scenario 3: Add Contact on Phone

```dart
// User added new contact
Future<void> onContactAdded(Contact newContact) async {
  // Incremental sync - just add
  final result = await api.incrementalSync(
    added: [newContact],
    removed: [],
  );

  // Check if newly added contact is registered
  if (result['new_registrations'] > 0) {
    await showContactJoinedNotification(newContact);
  }
}
```

### Scenario 4: Regular Background Sync

```dart
// Periodic sync (e.g., daily)
Future<void> regularSync() async {
  final deviceContacts = await getDeviceContacts();

  // Incremental sync - check for changes
  final added = deviceContacts
    .where((c) => !localContacts.contains(c))
    .toList();
  final removed = localContacts
    .where((c) => !deviceContacts.contains(c))
    .toList();

  if (added.isNotEmpty || removed.isNotEmpty) {
    await api.incrementalSync(added: added, removed: removed);
  }

  // Also check for new registrations
  await api.sync();
}
```

### Scenario 5: Handle New User Registration Notifications

```dart
// When app starts, check for pending notifications
Future<void> checkPendingNotifications() async {
  final registeredContacts = await api.getRegisteredContacts();

  for (final contact in registeredContacts) {
    if (contact['user'] != null && !contact['notified']) {
      // Show in-app notification: "John Doe joined Hamro!"
      await showNotification(
        title: "Contact joined!",
        body: "${contact['display_name']} is now on Hamro",
        data: contact['user'],
      );

      // Mark as notified
      await api.markNotified([contact['id']]);
    }
  }
}
```

---

## Database Schema

### user_contacts Table

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT | Primary key |
| user_id | BIGINT | Owner user |
| contact_value | VARCHAR | Original phone/email |
| contact_type | ENUM | 'phone' or 'email' |
| normalized_value | VARCHAR | E164/lowercase for matching |
| contact_label | VARCHAR | Mobile, home, work, etc. |
| display_name | VARCHAR | Contact's name |
| is_registered | BOOLEAN | Is contact a registered user |
| registered_user_id | BIGINT | Reference to registered user |
| notified_joined | BOOLEAN | Did we notify about joining |
| registered_at | TIMESTAMP | When contact became registered |
| created_at, updated_at | TIMESTAMP | Laravel timestamps |

### Indexes

```sql
CREATE INDEX idx_user_contacts_user_type ON user_contacts(user_id, contact_type);
CREATE INDEX idx_user_contacts_user_registered ON user_contacts(user_id, is_registered);
CREATE INDEX idx_user_contacts_normalized ON user_contacts(normalized_value);
```

### 1. Flutter / Dart

```dart
class FindContactsApi {
  final String _baseUrl;
  final String _token;

  FindContactsApi({
    required String baseUrl,
    required String token,
  }) : _baseUrl = baseUrl,
       _token = token;

  Future<List<FoundContact>> findContacts(List<String> contacts) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/api/v1/contacts/find'),
      headers: {
        'Authorization': 'Bearer $_token',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: jsonEncode({'contacts': contacts}),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['data'] as List)
          .map((e) => FoundContact.fromJson(e))
          .toList();
    } else if (response.statusCode == 429) {
      throw FindContactsException(
        'Rate limit exceeded. Please wait before retrying.',
        retryAfter: 60,
      );
    } else {
      throw FindContactsException('Failed to find contacts');
    }
  }
}

class FoundContact {
  final String contact;
  final bool found;
  final UserProfile? user;
  final String? duplicate;

  FoundContact({
    required this.contact,
    required this.found,
    this.user,
    this.duplicate,
  });

  factory FoundContact.fromJson(Map<String, dynamic> json) {
    return FoundContact(
      contact: json['contact'],
      found: json['found'],
      user: json['user'] != null ? UserProfile.fromJson(json['user']) : null,
      duplicate: json['duplicate'],
    );
  }
}

class UserProfile {
  final String id;
  final String name;
  final String email;
  final String? mobileNumber;
  final String? username;
  final String? avatarUrl;

  UserProfile({
    required this.id,
    required this.name,
    required this.email,
    this.mobileNumber,
    this.username,
    this.avatarUrl,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'],
      name: json['name'],
      email: json['email'],
      mobileNumber: json['mobile_number'],
      username: json['username'],
      avatarUrl: json['avatar_url'],
    );
  }
}
```

### 2. React Native / JavaScript

```typescript
interface Contact {
  contact: string;
  found: boolean;
  user: UserProfile | null;
  duplicate: string | null;
}

interface UserProfile {
  id: string;
  name: string;
  email: string;
  mobile_number: string;
  username: string;
  avatar_url: string;
}

interface FindContactsResponse {
  data: Contact[];
  meta: {
    total_requested: number;
    total_found: number;
  };
}

class FindContactsApi {
  private baseUrl: string;
  private token: string;

  constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  async findContacts(contacts: string[]): Promise<Contact[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/contacts/find`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ contacts }),
    });

    if (response.status === 429) {
      throw new Error('Rate limit exceeded. Please wait before retrying.');
    }

    if (!response.ok) {
      throw new Error('Failed to find contacts');
    }

    const data: FindContactsResponse = await response.json();
    return data.data;
  }
}
```

### 3. Android / Kotlin

```kotlin
data class Contact(
    val contact: String,
    val found: Boolean,
    val user: UserProfile?,
    val duplicate: String?
)

data class UserProfile(
    val id: String,
    val name: String,
    val email: String,
    val mobileNumber: String?,
    val username: String?,
    val avatarUrl: String?
)

data class FindContactsResponse(
    val data: List<Contact>,
    val meta: Meta
)

class FindContactsApi(
    private val baseUrl: String,
    private val token: String
) {
    private val client = OkHttpClient()

    suspend fun findContacts(contacts: List<String>): List<Contact> {
        val json = JSONObject().put("contacts", JSONArray(contacts))

        val request = Request.Builder()
            .url("$baseUrl/api/v1/contacts/find")
            .post(RequestBody.create(MediaType.parse("application/json"), json.toString()))
            .addHeader("Authorization", "Bearer $token")
            .addHeader("Content-Type", "application/json")
            .addHeader("Accept", "application/json")
            .build()

        return withContext(Dispatchers.IO) {
            val response = client.newCall(request).execute()

            when (response.code()) {
                200 -> {
                    val body = JSONObject(response.body()?.string())
                    val dataArray = body.getJSONArray("data")
                    (0 until dataArray.length()).map { i ->
                        val obj = dataArray.getJSONObject(i)
                        Contact(
                            contact = obj.getString("contact"),
                            found = obj.getBoolean("found"),
                            user = obj.optJSONObject("user")?.let { userObj ->
                                UserProfile(
                                    id = userObj.getString("id"),
                                    name = userObj.getString("name"),
                                    email = userObj.getString("email"),
                                    mobileNumber = userObj.optString("mobile_number").takeIf { it.isNotEmpty() },
                                    username = userObj.optString("username").takeIf { it.isNotEmpty() },
                                    avatarUrl = userObj.optString("avatar_url").takeIf { it.isNotEmpty() }
                                )
                            },
                            duplicate = obj.optString("duplicate").takeIf { it.isNotEmpty() && it != "null" }
                        )
                    }
                }
                429 -> throw RateLimitException("Too many requests")
                else -> throw FindContactsException("Failed to find contacts")
            }
        }
    }
}
```

---

## Best Practices

### 1. Batch Processing Large Contact Lists

```dart
Future<List<FoundContact>> syncAllContacts(List<String> allContacts) async {
  const batchSize = 100;
  final allResults = <FoundContact>[];

  for (var i = 0; i < allContacts.length; i += batchSize) {
    final batch = allContacts.skip(i).take(batchSize).toList();

    try {
      final results = await _api.findContacts(batch);
      allResults.addAll(results);

      // Small delay between batches to be respectful
      if (i + batchSize < allContacts.length) {
        await Future.delayed(Duration(milliseconds: 500));
      }
    } catch (e) {
      // Log error but continue with next batch
      debugPrint('Batch failed at index $i: $e');
    }
  }

  return allResults;
}
```

### 2. Filtering Registered Users

```dart
List<UserProfile> getRegisteredUsers(List<FoundContact> contacts) {
  return contacts
      .where((c) => c.found && c.user != null)
      .map((c) => c.user!)
      .toList();
}

// To also get which contacts matched
Map<UserProfile, List<String>> getUsersWithMatchedContacts(List<FoundContact> contacts) {
  final Map<String, List<String>> userContacts = {};
  final Map<String, UserProfile> userMap = {};

  for (final contact in contacts) {
    if (contact.found && contact.user != null) {
      final userId = contact.user!.id;
      userContacts.putIfAbsent(userId, () => []).add(contact.contact);
      userMap[userId] = contact.user!;
    }
  }

  return userMap.map((id, user) => MapEntry(user, userContacts[id]!));
}
```

### 3. Handling Duplicate Matches

```dart
// When the same user is matched by both phone and email
void handleDuplicates(List<FoundContact> contacts) {
  for (final contact in contacts) {
    if (contact.duplicate != null) {
      // This contact matches same user as another contact
      // Use `duplicate` to show the relationship
      debugPrint('${contact.contact} is same user as ${contact.duplicate}');
    }
  }
}
```

### 4. Initial Contact Sync Strategy

```dart
Future<void> syncContacts(List<String> deviceContacts) async {
  // 1. Get existing registered users from local DB
  final localUsers = await _db.users.toList();
  final localContactSet = localUsers.map((u) => u.email).toSet();

  // 2. Find new contacts to check
  final newContacts = deviceContacts
      .where((c) => !localContactSet.contains(c))
      .toList();

  // 3. Batch search
  final foundContacts = await findContacts(newContacts);

  // 4. Update local database
  for (final contact in foundContacts) {
    if (contact.found && contact.user != null) {
      await _db.users.put(contact.user!.id, contact.user!);
    }
  }
}
```

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /api/v1/contacts/find` | 10 requests | Per minute |

If you exceed the rate limit, you'll receive a `429 Too Many Requests` response. Implement exponential backoff in your retry logic.

```dart
Future<T> withRetry(Future<T> Function() request) async {
  const maxRetries = 3;
  var delay = Duration(seconds: 1);

  for (var i = 0; i < maxRetries; i++) {
    try {
      return await request();
    } on RateLimitException {
      if (i < maxRetries - 1) {
        await Future.delayed(delay);
        delay *= 2; // Exponential backoff
      }
    }
  }

  throw Exception('Max retries exceeded');
}
```

---

## Database Indexes

For optimal performance, ensure these indexes exist on the `users` table:

```sql
-- Email lookup
CREATE INDEX idx_users_email ON users(email);

-- Phone number lookup
CREATE INDEX idx_users_mobile_number ON users(mobile_number);
```

---

## Support

For issues or questions:
- Email: support@hamro.com
- Documentation: https://hamro.com/developer-docs