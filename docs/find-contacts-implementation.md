# Find Contacts - Implementation Examples

This directory contains code examples for integrating the Find Contacts API into your mobile application.

## Directory Structure

```
docs/
├── find-contacts-api.md              # Full API documentation
├── find-contacts-api.postman_collection.json  # Postman collection
└── integration/
    ├── flutter/
    │   └── find_contacts_example.dart
    ├── react-native/
    │   └── FindContactsApi.ts
    └── android/
        └── FindContactsApi.kt
```

---

## Quick Start

### 1. Get User Contacts from Device

#### Flutter
```dart
import 'package:contacts_service/contacts_service.dart';

Future<List<String>> getDeviceContacts() async {
  final contacts = await ContactsService.getContacts();
  final identifiers = <String>[];

  for (final contact in contacts) {
    // Add phone numbers
    for (final phone in contact.phones ?? []) {
      if (phone.value != null) {
        identifiers.add(phone.value!);
      }
    }
    // Add emails
    for (final email in contact.emails ?? []) {
      if (email.value != null) {
        identifiers.add(email.value!);
      }
    }
  }

  return identifiers;
}
```

#### React Native
```typescript
import Contacts from 'react-native-contacts';

async function getDeviceContacts(): Promise<string[]> {
  const permission = await Contacts.requestPermission();

  if (permission !== 'authorized') {
    throw new Error('Contacts permission denied');
  }

  const contacts = await Contacts.getAll();
  const identifiers: string[] = [];

  for (const contact of contacts) {
    // Add phone numbers
    if (contact.phoneNumbers) {
      for (const phone of contact.phoneNumbers) {
        if (phone.number) {
          identifiers.push(phone.number);
        }
      }
    }
    // Add emails
    if (contact.emailAddresses) {
      for (const email of contact.emailAddresses) {
        if (email.email) {
          identifiers.push(email.email);
        }
      }
    }
  }

  return identifiers;
}
```

#### Android (Kotlin)
```kotlin
import android.content.ContentResolver
import android.provider.ContactsContract

fun getDeviceContacts(contentResolver: ContentResolver): List<String> {
    val identifiers = mutableListOf<String>()
    val cursor = contentResolver.query(
        ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
        arrayOf(
            ContactsContract.CommonDataKinds.Phone.NUMBER,
            ContactsContract.CommonDataKinds.Email.ADDRESS
        ),
        null, null, null
    )

    cursor?.use {
        val phoneIndex = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
        val emailIndex = it.getColumnIndex(ContactsContract.CommonDataKinds.Email.ADDRESS)

        while (it.moveToNext()) {
            val phone = it.getString(phoneIndex)
            val email = it.getString(emailIndex)

            if (!phone.isNullOrEmpty()) identifiers.add(phone)
            if (!email.isNullOrEmpty()) identifiers.add(email)
        }
    }

    return identifiers
}
```

---

### 2. Sync Contacts with Server

#### Flutter
```dart
class ContactSyncService {
  final FindContactsApi _api;
  final LocalDatabase _db;

  Future<SyncResult> syncContacts() async {
    // 1. Get device contacts
    final deviceContacts = await getDeviceContacts();

    // 2. Remove already synced (optional optimization)
    final newContacts = await filterUnsyncedContacts(deviceContacts);

    // 3. Batch search server
    final results = await _api.findContacts(newContacts);

    // 4. Update local database
    int newUsers = 0;
    for (final result in results) {
      if (result.found && result.user != null) {
        await _db.users.upsert(result.user!);
        await _db.contactMapping.upsert(
          contact: result.contact,
          userId: result.user!.id,
        );
        newUsers++;
      }
    }

    return SyncResult(
      totalChecked: deviceContacts.length,
      newUsersFound: newUsers,
    );
  }

  Future<List<String>> filterUnsyncedContacts(List<String> all) async {
    final existing = await _db.contactMapping.getAllContacts();
    return all.where((c) => !existing.contains(c)).toList();
  }
}

class SyncResult {
  final int totalChecked;
  final int newUsersFound;

  SyncResult({required this.totalChecked, required this.newUsersFound});
}
```

#### React Native
```typescript
class ContactSyncService {
  constructor(
    private api: FindContactsApi,
    private storage: AsyncStorage
  ) {}

  async syncContacts(): Promise<SyncResult> {
    // 1. Get device contacts
    const deviceContacts = await getDeviceContacts();

    // 2. Filter already synced
    const newContacts = await this.filterUnsyncedContacts(deviceContacts);

    // 3. Batch search
    const results = await this.api.findContacts(newContacts);

    // 4. Update storage
    let newUsers = 0;
    for (const result of results) {
      if (result.found && result.user) {
        await this.storage.set(`user:${result.user.id}`, JSON.stringify(result.user));
        await this.storage.set(`mapping:${result.contact}`, result.user.id);
        newUsers++;
      }
    }

    return { totalChecked: deviceContacts.length, newUsersFound: newUsers };
  }

  async filterUnsyncedContacts(all: string[]): Promise<string[]> {
    const existing = await this.storage.getAllKeys();
    return all.filter(c => !existing.includes(`mapping:${c}`));
  }
}

interface SyncResult {
  totalChecked: number;
  newUsersFound: number;
}
```

---

### 3. Display Contact List with Registration Status

#### Flutter Widget
```dart
class ContactListWidget extends StatelessWidget {
  final List<DeviceContact> contacts;
  final Map<String, UserProfile?> registeredUsers;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: contacts.length,
      itemBuilder: (context, index) {
        final contact = contacts[index];
        final user = registeredUsers[contact.primaryIdentifier];

        return ListTile(
          leading: CircleAvatar(
            backgroundImage: user?.avatarUrl != null
                ? NetworkImage(user!.avatarUrl!)
                : null,
            child: user == null ? Icon(Icons.person) : null,
          ),
          title: Text(contact.displayName),
          subtitle: Text(
            user != null
                ? 'On Hamro'
                : contact.primaryIdentifier,
          ),
          trailing: user != null
              ? Container(
                  padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green.shade100,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'Registered',
                    style: TextStyle(color: Colors.green, fontSize: 12),
                  ),
                )
              : null,
          onTap: user != null
              ? () => _startConversation(user)
              : () => _inviteToJoin(contact),
        );
      },
    );
  }

  void _startConversation(UserProfile user) {
    // Navigate to chat creation
  }

  void _inviteToJoin(DeviceContact contact) {
    // Show invite dialog
  }
}
```

#### React Native Component
```tsx
import React from 'react';
import { View, Text, Image, TouchableOpacity, FlatList } from 'react-native';

interface Props {
  contacts: DeviceContact[];
  registeredUsers: Map<string, UserProfile>;
}

export const ContactList: React.FC<Props> = ({ contacts, registeredUsers }) => {
  const renderItem = ({ item: contact }) => {
    const user = registeredUsers.get(contact.primaryIdentifier);

    return (
      <TouchableOpacity
        style={styles.row}
        onPress={() => user ? startChat(user) : inviteToJoin(contact)}
      >
        <Image
          source={user?.avatarUrl ? { uri: user.avatarUrl } : null}
          style={styles.avatar}
          defaultSource={require('./avatar-placeholder.png')}
        />
        <View style={styles.info}>
          <Text style={styles.name}>{contact.displayName}</Text>
          <Text style={styles.subtitle}>
            {user ? 'On Hamro' : contact.primaryIdentifier}
          </Text>
        </View>
        {user && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>Registered</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <FlatList
      data={contacts}
      renderItem={renderItem}
      keyExtractor={item => item.primaryIdentifier}
    />
  );
};
```

---

### 4. Debouncing & Batching Strategy

```dart
class ContactSyncManager {
  final FindContactsApi _api;
  final List<String> _pendingContacts = [];
  Timer? _debounceTimer;
  bool _isSyncing = false;

  static const int batchSize = 100;
  static const Duration debounceInterval = Duration(seconds: 2);

  void addContacts(List<String> contacts) {
    _pendingContacts.addAll(contacts);
    _debounceTimer?.cancel();
    _debounceTimer = Timer(debounceInterval, _processSync);
  }

  Future<void> _processSync() async {
    if (_isSyncing || _pendingContacts.isEmpty) return;

    _isSyncing = true;

    while (_pendingContacts.isNotEmpty) {
      final batch = _pendingContacts.take(batchSize).toList();
      _pendingContacts.removeRange(0, batch.length.clamp(0, batch.length));

      try {
        final results = await _api.findContacts(batch);

        // Update UI and database
        for (final result in results) {
          if (result.found) {
            _emitUserFound(result.user!);
          }
        }
      } catch (e) {
        // Handle error, maybe retry
        _pendingContacts.insertAll(0, batch);
        break;
      }

      // Small delay between batches
      await Future.delayed(Duration(milliseconds: 200));
    }

    _isSyncing = false;
  }
}
```

---

### 5. Handling Offline/Failed Sync

```dart
class OfflineContactSync {
  final FindContactsApi _api;
  final Queue<SyncBatch> _failedBatches = Queue();

  Future<void> retryFailedBatches() async {
    while (_failedBatches.isNotEmpty) {
      final batch = _failedBatches.removeFirst();

      try {
        await _api.findContacts(batch.contacts);
        // Success - notify sync complete
      } on NetworkException {
        // Put back at front of queue
        _failedBatches.addFirst(batch);
        // Wait before retry
        await Future.delayed(Duration(seconds: 30));
      }
    }
  }

  void onSyncComplete(List<FoundContact> results) {
    // Update local cache
    for (final result in results) {
      if (result.found) {
        _cacheUser(result.user!);
        _markContactSynced(result.contact);
      }
    }
  }
}
```

---

## Error Handling Reference

| HTTP Status | Error Type | Action |
|-------------|------------|--------|
| 200 | Success | Process results |
| 401 | Unauthorized | Redirect to login |
| 422 | Validation | Check request format |
| 429 | Rate Limited | Wait and retry |
| 500 | Server Error | Log and retry with backoff |

---

## Performance Tips

1. **Deduplicate contacts before sending** - Remove duplicate phone numbers/emails from device
2. **Use incremental sync** - Only send new contacts, not full list every time
3. **Cache results locally** - Don't re-fetch known users
4. **Batch appropriately** - Send 100 at a time (maximum)
5. **Handle rate limits** - Implement exponential backoff