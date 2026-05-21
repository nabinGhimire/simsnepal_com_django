# FCM Push Notification System - Mobile Developer Guide

## Overview
This app uses Firebase Cloud Messaging (FCM) to send **data messages** (not notification messages) to allow custom UI and interactive action buttons.

**Key Points:**
- **Actions are handled by backend**: When user taps a button, the app calls our API endpoint, and the backend performs the action (creates threads, adds participants, etc.)
- **Business apps can use this system**: Business platforms can send notifications via our API (for channel messages, group approvals, etc.)
- **Auto-admin**: When business apps create channels/groups, the creating user is automatically added as admin.
- **In-App Notifications**: Backend automatically creates in-app notifications when sending FCM messages. Fetch from `GET /api/v1/auth/notifications`.

---

## 1. FCM Token Registration

### Getting the FCM Token

**Android (Kotlin)**:
```kotlin
FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
    if (task.isSuccessful) {
        val token = task.result
        registerTokenWithBackend(token, "android", deviceName)
    }
}
```

**iOS (Swift)**:
```swift
Messaging.messaging().token { token, error in
    if let token = token {
        registerTokenWithBackend(token, "ios", UIDevice.current.name)
    }
}
```

### Registering Token with Backend

**Endpoint**: `POST /api/v1/auth/devices/fcm-token`
**Headers**: `Authorization: Bearer {sanctum_token}`
**Content-Type**: `application/json`

**Payload**:
```json
{
    "device_identifier": "unique-device-id",  // Use UUID or Firebase Instance ID
    "fcm_token": "fcm-token-from-firebase",
    "device_name": "Samsung Galaxy S21",  // Optional
    "platform": "android"  // or "ios", "web"
}
```

**Response**:
```json
{
    "message": "FCM token registered successfully.",
    "device_id": "uuid-of-device-record"
}
```

### On Logout (Remove Token)

**Endpoint**: `DELETE /api/v1/auth/devices/fcm-token`
**Payload**:
```json
{
    "device_identifier": "unique-device-id"
}
```

---

## 2. Handling Data Messages

### Android (Kotlin)

Data messages are received in `FirebaseMessagingService.onMessageReceived()`:

```kotlin
override fun onMessageReceived(remoteMessage: RemoteMessage) {
    val data = remoteMessage.data
    
    val title = data["title"] ?: ""
    val body = data["body"] ?: ""
    val imageUrl = data["image"] ?: ""
    val actionsJson = data["actions"] ?: "[]"
    val route = data["route"] ?: ""
    val type = data["type"] ?: "plain"
    
    // Parse actions
    val actions = JSONArray(actionsJson)
    val actionList = mutableListOf<NotificationAction>()
    
    for (i in 0 until actions.length()) {
        val action = actions.getJSONObject(i)
        actionList.add(
            NotificationAction(
                actionId = action.getString("action"),
                text = action.getString("text")
            )
        )
    }
    
    // Show notification with actions
    showNotificationWithActions(title, body, imageUrl, actionList, route, type, data)
}
```

**Creating Notification with Actions (Android)**:
```kotlin
fun showNotificationWithActions(
    title: String,
    body: String,
    imageUrl: String,
    actions: List<NotificationAction>,
    route: String,
    type: String,
    data: Map<String, String>
) {
    val channelId = "hamro_notifications"
    val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    
    // Create notification channel (Android 8+)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        val channel = NotificationChannel(channelId, "Hamro Notifications", NotificationManager.IMPORTANCE_HIGH)
        manager.createNotificationChannel(channel)
    }
    
    val builder = NotificationCompat.Builder(this, channelId)
        .setContentTitle(title)
        .setContentText(body)
        .setSmallIcon(R.drawable.ic_notification)
        .setAutoCancel(true)
    
    // Add image if present
    if (imageUrl.isNotEmpty()) {
        // Load image and set as big picture
        val bitmap = loadBitmapFromUrl(imageUrl)
        builder.setStyle(NotificationCompat.BigPictureStyle().bigPicture(bitmap))
    }
    
    // Add action buttons
    actions.forEach { action ->
        val intent = Intent(this, NotificationActionReceiver::class.java).apply {
            putExtra("action", action.actionId)
            putExtra("route", route)
            putExtra("type", type)
            // Add all data as extras
            data.forEach { (key, value) ->
                putExtra(key, value)
            }
        }
        
        val pendingIntent = PendingIntent.getBroadcast(
            this,
            action.actionId.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
        )
        
        builder.addAction(0, action.text, pendingIntent)
    }
    
    // Set tap action (navigate to route)
    val tapIntent = Intent(this, MainActivity::class.java).apply {
        putExtra("route", route)
        putExtra("type", type)
        data.forEach { (key, value) ->
            putExtra(key, value)
        }
    }
    val tapPendingIntent = PendingIntent.getActivity(
        this,
        0,
        tapIntent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
    )
    builder.setContentIntent(tapPendingIntent)
    
    manager.notify(System.currentTimeMillis().toInt(), builder.build())
}
```

### iOS (Swift)

**AppDelegate.swift** (iOS < 10) or **UNUserNotificationCenterDelegate** (iOS 10+):

```swift
// Handle data messages (in iOS, these are delivered to app delegate)
func application(_ application: UIApplication, 
                 didReceiveRemoteNotification userInfo: [AnyHashable : Any],
                 fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
    
    guard let type = userInfo["type"] as? String else {
        completionHandler(.failed)
        return
    }
    
    let title = userInfo["title"] as? String ?? ""
    let body = userInfo["body"] as? String ?? ""
    let imageUrl = userInfo["image"] as? String ?? ""
    let route = userInfo["route"] as? String ?? ""
    let actionsJson = userInfo["actions"] as? String ?? "[]"
    
    // Parse actions
    if let actionsData = actionsJson.data(using: .utf8),
       let actions = try? JSONSerialization.jsonObject(with: actionsData) as? [[String: Any]] {
        
        // Show notification with actions
        showNotificationWithActions(title: title, body: body, imageUrl: imageUrl, actions: actions, route: route, type: type, userInfo: userInfo)
    }
    
    completionHandler(.newData)
}

// iOS 10+ - UNUserNotificationCenterDelegate
func userNotificationCenter(_ center: UNUserNotificationCenter,
                            didReceive response: UNNotificationResponse,
                            withCompletionHandler completionHandler: @escaping () -> Void) {
    
    let userInfo = response.notification.request.content.userInfo
    let route = userInfo["route"] as? String ?? ""
    
    // Handle action button tap
    if let actionId = response.actionIdentifier {
        handleNotificationAction(actionId: actionId, userInfo: userInfo)
    } else {
        // Notification tapped - navigate to route
        navigateToRoute(route)
    }
    
    completionHandler()
}

func showNotificationWithActions(title: String, body: String, imageUrl: String, 
                            actions: [[String: Any]], route: String, 
                            type: String, userInfo: [AnyHashable: Any]) {
    
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body
    content.userInfo = userInfo
    
    // Add image attachment if present
    if !imageUrl.isEmpty {
        if let url = URL(string: imageUrl) {
            let attachment = try? UNNotificationAttachment(identifier: "", url: url)
            if let attachment = attachment {
                content.attachments = [attachment]
            }
        }
    }
    
    var notificationActions: [UNNotificationAction] = []
    
    for action in actions {
        if let actionId = action["action"] as? String,
           let text = action["text"] as? String {
            let notificationAction = UNNotificationAction(
                identifier: actionId,
                title: text,
                options: [.foreground]
            )
            notificationActions.append(notificationAction)
        }
    }
    
    // Create category with actions
    let category = UNNotificationCategory(
        identifier: type,
        actions: notificationActions,
        intentIdentifiers: [],
        options: []
    )
    
    UNUserNotificationCenter.current().setNotificationCategories([category])
    content.categoryIdentifier = type
    
    let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
    UNUserNotificationCenter.current().add(request)
}
```

**Register Notification Categories (in AppDelegate)**:
```swift
func registerNotificationCategories() {
    // Friend request
    let acceptFriend = UNNotificationAction(identifier: "accept_friend", title: "Accept", options: [.foreground])
    let rejectFriend = UNNotificationAction(identifier: "reject_friend", title: "Reject", options: [.foreground])
    
    let friendRequestCategory = UNNotificationCategory(
        identifier: "friend_request",
        actions: [acceptFriend, rejectFriend],
        intentIdentifiers: [],
        options: []
    )
    
    // Group join request
    let allowGroupJoin = UNNotificationAction(identifier: "allow_group_join", title: "Allow", options: [.foreground])
    let rejectGroupJoin = UNNotificationAction(identifier: "reject_group_join", title: "Reject", options: [.foreground])
    
    let groupJoinCategory = UNNotificationCategory(
        identifier: "group_join_request",
        actions: [allowGroupJoin, rejectGroupJoin],
        intentIdentifiers: [],
        options: []
    )
    
    // Channel join request
    let allowChannelJoin = UNNotificationAction(identifier: "allow_channel_join", title: "Allow", options: [.foreground])
    let rejectChannelJoin = UNNotificationAction(identifier: "reject_channel_join", title: "Reject", options: [.foreground])
    
    let channelJoinCategory = UNNotificationCategory(
        identifier: "channel_join_request",
        actions: [allowChannelJoin, rejectChannelJoin],
        intentIdentifiers: [],
        options: []
    )
    
    // Multi-device login
    let acceptLogin = UNNotificationAction(identifier: "accept_login", title: "Accept", options: [.foreground])
    let rejectLogin = UNNotificationAction(identifier: "reject_login", title: "Reject", options: [.foreground])
    
    let loginCategory = UNNotificationCategory(
        identifier: "multi_device_login",
        actions: [acceptLogin, rejectLogin],
        intentIdentifiers: [],
        options: []
    )
    
    UNUserNotificationCenter.current().setNotificationCategories([friendRequestCategory, groupJoinCategory, channelJoinCategory, loginCategory])
}
```

---

## 3. Notification Payload Structure

**Example Data Message Payload**:
```json
{
    "title": "New Friend Request",
    "body": "John Doe sent you a friend request.",
    "image": "https://example.com/storage/images/user-id/image.jpg",
    "actions": [
        {"action": "accept_friend", "text": "Accept"},
        {"action": "reject_friend", "text": "Reject"}
    ],
    "route": "/friend-request/123",
    "type": "friend_request",
    "sender_id": "user-uuid",
    "sender_name": "John Doe",
    "request_id": "request-uuid"
}
```

**Payload Fields**:
- `title`: Notification title
- `body`: Notification body text
- `image`: (Optional) URL of image to show in notification
- `actions`: Array of action objects with `action` (actionId) and `text` (button text)
- `route`: Deep link path (e.g., `/chat/123`, `/friend-request/456`)
- `type`: Notification type (`friend_request`, `group_join_request`, `channel_join_request`, `multi_device_login`, `channel_message`, `plain`, `system`)
- `...`: Any extra custom data (e.g., `sender_id`, `group_id`, `channel_id`, etc.)

---

## 4. Deep Linking

When user taps a notification (or an action button), navigate to the screen specified in `route`:

**Android**:
```kotlin
fun navigateToRoute(route: String, data: Map<String, String>) {
    val intent = when {
        route.startsWith("/chat/") -> {
            val threadId = route.removePrefix("/chat/")
            Intent(this, ChatActivity::class.java).apply {
                putExtra("thread_id", threadId)
            }
        }
        route.startsWith("/friend-request/") -> {
            val requestId = route.removePrefix("/friend-request/")
            Intent(this, FriendRequestActivity::class.java).apply {
                putExtra("request_id", requestId)
            }
        }
        route.startsWith("/group/") -> {
            Intent(this, GroupActivity::class.java).apply {
                putExtra("group_id", route.substringAfterLast("/"))
            }
        }
        route.startsWith("/channel/") -> {
            Intent(this, ChannelActivity::class.java).apply {
                putExtra("channel_id", route.substringAfterLast("/"))
            }
        }
        else -> Intent(this, MainActivity::class.java)
    }
    startActivity(intent)
}
```

**iOS**:
```swift
func navigateToRoute(_ route: String) {
    if route.hasPrefix("/chat/") {
        let threadId = route.components(separatedBy: "/").last ?? ""
        let chatVC = ChatViewController()
        chatVC.threadId = threadId
        navigationController?.pushViewController(chatVC, animated: true)
    } else if route.hasPrefix("/friend-request/") {
        // Navigate to friend request screen
    } else if route.hasPrefix("/group/") {
        // Navigate to group screen
    } else if route.hasPrefix("/channel/") {
        // Navigate to channel screen
    }
}
```

---

## 5. Handling Action Button Clicks

When user taps an action button (Accept/Reject), send the action to the backend:

**Endpoint**: `POST /api/v1/auth/notifications/fcm-action`
**Headers**: `Authorization: Bearer {sanctum_token}`
**Content-Type**: `application/json`

**Payload**:
```json
{
    "action": "accept_friend",  // or "reject_friend", "allow_group_join", etc.
    "type": "friend_request",  // or "group_join_request", "channel_join_request", "multi_device_login", etc.
    "notification_id": "notification-uuid",  // ID of the in-app notification to mark as read
    "request_id": "request-uuid",  // if applicable
    "sender_id": "sender-uuid",  // if applicable
    "group_id": "group-uuid",  // if applicable
    "channel_id": "channel-uuid",  // if applicable
    "new_device_id": "device-id",  // for multi-device login
    "user_id": "user-uuid"  // for multi-device login
}
```

**Response**:
```json
{
    "message": "Friend request accepted.",
    "thread_id": "thread-uuid"  // if applicable
}
```

**How Backend Handles Actions:**
- **Friend Request Accept**: Backend creates friendship, creates private thread, deletes pending request
- **Group Join Allow**: Backend adds participant to group*
- **Channel Join Allow**: Backend adds participant to channel (thread with `is_channel=true`)*
- **Multi-Device Login Accept**: Backend marks device as verified, allows login*

**Android Example**:
```kotlin
fun handleAction(actionId: String, data: Map<String, String>) {
    val type = data["type"] ?: ""
    
    val payload = hashMapOf(
        "action" to actionId,
        "type" to type
    )
    
    // Add relevant IDs
    data["request_id"]?.let { payload["request_id"] = it }
    data["sender_id"]?.let { payload["sender_id"] = it }
    data["group_id"]?.let { payload["group_id"] = it }
    data["channel_id"]?.let { payload["channel_id"] = it }
    data["new_device_id"]?.let { payload["new_device_id"] = it }
    data["user_id"]?.let { payload["user_id"] = it }
    
    // Send to backend
    apiService.postNotificationAction(payload).enqueue(object : Callback<JsonObject> {
        override fun onResponse(call: Call<JsonObject>, response: Response<JsonObject>) {
            // Handle success
        }
        override fun onFailure(call: Call<JsonObject>, t: Throwable) {
            // Handle failure
        }
    })
}
```

---

## 6. Platform-Specific Notes

### iOS
- **Entitlements**: Add `Push Notifications` capability in Xcode
- **Background Modes**: Enable `Remote notifications` in Background Modes
- **Notification Service Extension**: Optional, for downloading images before displaying notification
- **Interactive Notifications**: Register notification categories with actions in `AppDelegate`

### Android
- **Notification Channels**: Create channels for Android 8+ (API level 26+)
- **PendingIntent**: Use `FLAG_MUTABLE` for Android 12+ (API level 31+)
- **Big Picture Style**: Use `NotificationCompat.BigPictureStyle()` for image notifications
- **BroadcastReceiver**: Register a receiver for notification action button clicks*

### Web (Optional)
- Use Firebase Web SDK to receive messages
- Handle data messages in `onMessage` callback
- Show browser notifications using `Notification API`
- Note: Web push notifications have limited support for action buttons*

---

## 7. Testing

### Test FCM Token Registration
```bash
curl -X POST http://your-domain.com/api/v1/auth/devices/fcm-token \
  -H "Authorization: Bearer {sanctum_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "device_identifier": "test-device-123",
    "fcm_token": "test-fcm-token",
    "device_name": "Test Device",
    "platform": "android"
  }'
```

### Test Notification Action
```bash
curl -X POST http://your-domain.com/api/v1/auth/notifications/fcm-action \
  -H "Authorization: Bearer {sanctum_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "accept_friend",
    "type": "friend_request",
    "sender_id": "user-id",
    "request_id": "request-id"
  }'
```

---

## 8. Notification Scenarios

### Friend Request
- **Title**: "New Friend Request"
- **Body**: "{sender_name} sent you a friend request."
- **Image**: Sender's avatar URL
- **Actions**: Accept (action: `accept_friend`), Reject (action: `reject_friend`)
- **Route**: `/friend-request/{request_id}`
- **Backend handles**: Creates friendship, private thread*

### Group Join Request (to Admin)
- **Title**: "New Group Join Request"
- **Body**: "{requester_name} wants to join the group."
- **Image**: Requester's image URL
- **Actions**: Allow (action: `allow_group_join`), Reject (action: `reject_group_join`)
- **Route**: `/group/{group_id}/join-requests`
- **Backend handles**: Adds participant to group*

### Channel Join Request (to Admin)
- **Title**: "New Channel Join Request"
- **Body**: "{requester_name} wants to join the channel."
- **Image**: Requester's image URL
- **Actions**: Allow (action: `allow_channel_join`), Reject (action: `reject_channel_join`)
- **Route**: `/channel/{channel_id}/join-requests`
- **Backend handles**: Adds participant to channel (thread with `is_channel=true`)*

### Channel Message (to Participants)
- **Title**: Sender's name
- **Body**: Message text
- **Image**: Optional (channel image)
- **Actions**: None (tap to navigate)
- **Route**: `/channel/{channel_id}`
- **Backend handles**: Just notification, no action needed*

### Multi-Device Login Approval
- **Title**: "New Device Login Detected"
- **Body**: "A login attempt was detected from {device_name}. Do you want to allow this device?"
- **Image**: App logo URL
- **Actions**: Accept (action: `accept_login`), Reject (action: `reject_login`)
- **Route**: `/login-approval/{device_id}`
- **Backend handles**: Marks device as verified*

### Plain Notification
- **Title**: Custom
- **Body**: Custom
- **Image**: Optional
- **Actions**: None (tap to navigate)
- **Route**: Custom (e.g., `/chat/{thread_id}`)

### System Notification
- **Title**: Custom (e.g., "Verification Approved")
- **Body**: Custom
- **Image**: Optional
- **Actions**: None
- **Route**: Custom*

---

## 9. In-App Notifications (Mobile App Section)

The backend automatically creates in-app notifications when sending FCM push notifications. Your app should fetch and display these notifications in its notification section.

### Fetching Notifications from API

**Endpoint**: `GET /api/v1/auth/notifications`
**Headers**: `Authorization: Bearer {sanctum_token}`
**Query Parameters**:
- `type` (optional): Filter by type (`friend_request`, `group_join_request`, `channel_join_request`, `channel_message`, `multi_device_login`, `plain`, `system`)
- `unread_only` (optional): `true` to show only unread notifications
- `per_page` (optional): Items per page (default: 20)

**Response**:
```json
{
    "data": [
        {
            "id": "notification-uuid",
            "type": "friend_request",
            "title": "New Friend Request",
            "body": "John Doe sent you a friend request.",
            "image": "https://example.com/storage/images/user-id/image.jpg",
            "route": "/friend-request/123",
            "actions": [
                {"action": "accept_friend", "text": "Accept"},
                {"action": "reject_friend", "text": "Reject"}
            ],
            "data": { Extra custom data (sender_id, request_id, etc.) },
            "read_at": null,  // null means unread
            "created_at": "2026-05-01T10:30:00.000000Z"
        }
    ],
    "meta": {
        "current_page": 1,
        "per_page": 20,
        "total": 50,
        "last_page": 3
    }
}
```

**Android (Kotlin)**:
```kotlin
fun fetchNotifications(unreadOnly: Boolean = false, type: String? = null) {
    val params = mutableMapOf<String, String>()
    if (unreadOnly) params["unread_only"] = "true"
    type?.let { params["type"] = it }
    
    apiService.getNotifications(params).enqueue(object : Callback<JsonObject> {
        override fun onResponse(call: Call<JsonObject>, response: Response<JsonObject>) {
            val notifications = response.body()?.getAsJsonArray("data")
            displayNotifications(notifications)
        }
        override fun onFailure(call: Call<JsonObject>, t: Throwable) {
            // Handle error
        }
    })
}
```

**iOS (Swift)**:
```swift
func fetchNotifications(unreadOnly: Bool = false, type: String? = nil) {
    var params: [String: Any] = [:]
    if unreadOnly { params["unread_only"] = true }
    type?.let { params["type"] = $0 }
    
    apiService.getNotifications(params: params) { result in
        switch result {
        case .success(let response):
            let notifications = response["data"] as? [[String: Any]] ?? []
            displayNotifications(notifications)
        case .failure(let error):
            // Handle error
        }
    }
}
```

### Displaying Notifications
- Show `title`, `body`, `image` (if present) in your notification list
- Show unread notifications differently (e.g., bold title, blue dot*)
- Use `created_at` to sort by newest first
- Show action buttons if `actions` array is not empty

### Handling Notification Tap (Navigate Using `route`)

When user taps a notification, navigate to the screen specified in `route`:

**Android**:
```kotlin
fun onNotificationTapped(notification: JsonObject) {
    val route = notification["route"]?.asString ?: ""
    val type = notification["type"]?.asString ?: ""
    val data = notification["data"]?.asJsonObject
    
    // Mark as read
    notification["id"]?.asString?.let { markAsRead(it) }
    
    // Navigate
    navigateToRoute(route, type, data)
}
```

**iOS**:
```swift
func onNotificationTapped(_ notification: [String: Any]) {
    let route = notification["route"] as? String ?? ""
    let type = notification["type"] as? String ?? ""
    let data = notification["data"] as? [String: Any]
    
    // Mark as read
    if let id = notification["id"] as? String {
        markAsRead(id)
    }
    
    // Navigate
    navigateToRoute(route)
}
```

### Marking Notifications as Read

**Mark Single Notification as Read**:
**Endpoint**: `POST /api/v1/auth/notifications/{notification}/mark-read`
**Response**: `{"message": "Notification marked as read.", "notification": {...}}`

**Mark All as Read**:
**Endpoint**: `POST /api/v1/auth/notifications/mark-all-read`
**Response**: `{"message": "All notifications marked as read.", "updated_count": 5}`

**Get Unread Count**:
**Endpoint**: `GET /api/v1/auth/notifications/unread-count`
**Response**: `{"unread_count": 3}`

**Android**:
```kotlin
fun markAsRead(notificationId: String) {
    apiService.markAsRead(notificationId).enqueue(object : Callback<JsonObject> {
        override fun onResponse(call: Call<JsonObject>, response: Response<JsonObject>) {
            // Update UI - remove unread indicator
        }
        override fun onFailure(call: Call<JsonObject>, t: Throwable) {}
    })
}

fun markAllAsRead() {
    apiService.markAllAsRead().enqueue(object : Callback<JsonObject> {
        override fun onResponse(call: Call<JsonObject>, response: Response<JsonObject>) {
            val updatedCount = response.body()?.get("updated_count")?.asInt ?: 0
            // Update UI - clear all unread indicators
        }
        override fun onFailure(call: Call<JsonObject>, t: Throwable) {}
    })
}

fun getUnreadCount() {
    apiService.getUnreadCount().enqueue(object : Callback<JsonObject> {
        override fun onResponse(call: Call<JsonObject>, response: Response<JsonObject>) {
            val count = response.body()?.get("unread_count")?.asInt ?: 0
            updateBadge(count) // Update notification badge
        }
        override fun onFailure(call: Call<JsonObject>, t: Throwable) {}
    })
}
```

### Deleting Notifications

**Delete Single Notification**:
**Endpoint**: `DELETE /api/v1/auth/notifications/{notification}`

**Delete All Notifications**:
**Endpoint**: `DELETE /api/v1/auth/notifications/all`

### How Backend Creates Notifications
When the backend sends an FCM data message (via any method in `FcmNotificationService`), it **automatically creates an in-app notification record** in the `notifications` table.

This means:
1. Your app **doesn't need to create notifications** - the backend handles this
2. Just **fetch from `GET /api/v1/auth/notifications`** to display them
3. When user taps a notification, **navigate using the `route` field**
4. If it's an action button, **call `POST /api/v1/auth/notifications/fcm-action`** (as documented in Section 5)

---

## 10. For Business Apps

Business platforms can use this notification system via our API:

### Creating Channels/Groups
When a business app creates a channel or group, the creating user is **automatically added as admin**:

```bash
# Create channel (backend automatically adds creator as admin)
POST /api/v1/channels
{
    "name": "My Channel",
    "participants": [{"owner_id": "user1-uuid"}, {"owner_id": "user2-uuid"}]
}

# Create group (backend automatically adds creator as admin)
POST /api/v1/groups
{
    "name": "My Group",
    "participants": [{"owner_id": "user1-uuid"}, {"owner_id": "user2-uuid"}]
}
```

### Sending Notifications from Business Apps
Business apps can trigger notifications by:
1. **Creating content** (messages, join requests) - notifications are sent automatically
2. **Calling notification endpoints** - for custom notifications*

**Example: Business app sends channel message notification**:
```bash
# Backend (PHP) - when business app posts a message to channel:
$notificationService->sendChannelMessageNotification(
    $participants,  // Array of User models or FCM tokens
    $channelId,
    $senderName,
    $messageText,
    $channelImageUrl
);
```

---

## 11. Troubleshooting

### FCM Token Not Received
- Check Firebase configuration in app
- Ensure Google Play Services are installed (Android)
- Check APNs certificate (iOS)

### Notifications Not Shown
- Android: Check notification channel settings
- iOS: Check notification permissions
- Both: Verify data message structure*

### Actions Not Working
- Android: Verify PendingIntent flags
- iOS: Verify notification category registration
- Both: Check action endpoint payload*

### Backend Actions Not Working
- Check API endpoint: `POST /api/v1/auth/notifications/fcm-action`
- Verify user is authorized (for group/channel actions, user must be admin)
- Check logs: `storage/logs/laravel.log`

### In-App Notifications Not Appearing
- Check API endpoint: `GET /api/v1/auth/notifications`
- Verify user is authenticated (Bearer token)`
- Check if backend is creating notifications (check `notifications` table in database)`
- Check logs for errors: `storage/logs/laravel.log`

---

**Contact Backend Team**: {backend-team-email}
**API Documentation**: {api-docs-url}
