# Email Templates Implementation Checklist

## 📊 Current Status

### Templates Created: ✅ 9/9 (100%)

- ✅ OTP Email
- ✅ Welcome Email
- ✅ Friend Request Email
- ✅ Password Reset Email (OTP-based instead)
- ✅ Notification Email (Generic)
- ✅ Message Notification Email
- ✅ Security Alert Email
- ✅ Call Notification Email
- ✅ Generic Custom Email

### Mailable Classes: ⚠️ 1/9 (11%)

- ✅ OtpMail - **FULLY IMPLEMENTED & WORKING**
- ❌ WelcomeUserMail - Needs implementation
- ❌ FriendRequestMail - Needs implementation
- ❌ MessageNotificationMail - Needs implementation
- ❌ CallNotificationMail - Needs implementation
- ❌ SecurityAlertMail - Needs implementation
- ❌ GenericNotificationMail - Needs implementation
- ✅ (Password Reset - Using OTP instead, don't need separate Mailable)

### Email Listeners: ❌ 0/6 (0%)

- ❌ SendWelcomeEmail
- ❌ SendFriendRequestEmail
- ❌ SendMessageNotificationEmail
- ❌ SendCallNotificationEmail
- ❌ SendSecurityAlertEmail
- ❌ Others...

---

## 🎯 Implementation Tasks

### PHASE 1: Welcome Email (High Priority)

**Purpose:** Greet new users after registration

- [ ] **Create Mailable Class**
    - File: `app/Mail/WelcomeUserMail.php`
    - Copy from: `app/Mail/ExampleMailables.php` → `WelcomeUserMail`
    - Location to trigger: After OTP verification in AuthController

- [ ] **Integration Point**
    - File: `app/Http/Controllers/Api/V1/Auth/AuthController.php`
    - Method: `verifyOtp()` - After successful verification
    - Code:
        ```php
        // After token creation in verifyOtp()
        Mail::to($user->email)->send(
            new WelcomeUserMail($user->getProviderName(), $user->id)
        );
        ```

**Files to Modify:**

- [ ] Create: `app/Mail/WelcomeUserMail.php`
- [ ] Modify: `app/Http/Controllers/Api/V1/Auth/AuthController.php` (verifyOtp method)

---

### PHASE 2: Friend Request Email (High Priority)

**Purpose:** Notify users of incoming friend requests

- [ ] **Create Mailable Class**
    - File: `app/Mail/FriendRequestMail.php`
    - Copy from: `app/Mail/ExampleMailables.php` → `FriendRequestMail`

- [ ] **Create Event Listener**
    - File: `app/Listeners/SendFriendRequestEmail.php`
    - Listens to: `FriendRequestEvent`
    - Location: `app/Events/FriendRequestEvent.php` (already exists)

- [ ] **Register Listener**
    - File: `app/Providers/EventServiceProvider.php`
    - Add to `$listen` array:
        ```php
        FriendRequestEvent::class => [
            SendFriendRequestEmail::class,
        ],
        ```

**Files to Create/Modify:**

- [ ] Create: `app/Mail/FriendRequestMail.php`
- [ ] Create: `app/Listeners/SendFriendRequestEmail.php`
- [ ] Modify: `app/Providers/EventServiceProvider.php`

---

### PHASE 3: Message Notification Email (Medium Priority)

**Purpose:** Notify offline users of new messages

- [ ] **Create Mailable Class**
    - File: `app/Mail/MessageNotificationMail.php`
    - Copy from: `app/Mail/ExampleMailables.php` → `MessageNotificationMail`

- [ ] **Create Event Listener**
    - File: `app/Listeners/SendMessageNotificationEmail.php`
    - Listens to: `NewMessageEvent`
    - Location: `app/Events/NewMessageEvent.php` (already exists)

- [ ] **Register Listener**
    - File: `app/Providers/EventServiceProvider.php`
    - Add:
        ```php
        NewMessageEvent::class => [
            SendMessageNotificationEmail::class,
        ],
        ```

**Files to Create/Modify:**

- [ ] Create: `app/Mail/MessageNotificationMail.php`
- [ ] Create: `app/Listeners/SendMessageNotificationEmail.php`
- [ ] Modify: `app/Providers/EventServiceProvider.php`

---

### PHASE 4: Call Notification Email (Medium Priority)

**Purpose:** Notify offline users of incoming calls

- [ ] **Create Mailable Class**
    - File: `app/Mail/CallNotificationMail.php`
    - Copy from: `app/Mail/ExampleMailables.php` → `CallNotificationMail`

- [ ] **Create Event Listener**
    - File: `app/Listeners/SendCallNotificationEmail.php`
    - Listens to: `CallStartedEvent`
    - Location: `app/Events/CallStartedEvent.php` (already exists)

- [ ] **Register Listener**
    - File: `app/Providers/EventServiceProvider.php`
    - Add:
        ```php
        CallStartedEvent::class => [
            SendCallNotificationEmail::class,
        ],
        ```

**Files to Create/Modify:**

- [ ] Create: `app/Mail/CallNotificationMail.php`
- [ ] Create: `app/Listeners/SendCallNotificationEmail.php`
- [ ] Modify: `app/Providers/EventServiceProvider.php`

---

### PHASE 5: Security Alert Email (Low Priority)

**Purpose:** Alert users of suspicious activity

- [ ] **Create Mailable Class**
    - File: `app/Mail/SecurityAlertMail.php`
    - Copy from: `app/Mail/ExampleMailables.php` → `SecurityAlertMail`

- [ ] **Decide When to Send**
    - New device login detected
    - Multiple failed login attempts
    - Password changed
    - Account activity from unusual location

- [ ] **Implementation**
    - Add checks in AuthController
    - Send security alert email when triggered

**Files to Create/Modify:**

- [ ] Create: `app/Mail/SecurityAlertMail.php`
- [ ] Modify: `app/Http/Controllers/Api/V1/Auth/AuthController.php`
- [ ] Consider creating: `app/Listeners/SecurityAlertListener.php`

---

### PHASE 6: Generic Notification Email (Optional)

**Purpose:** Flexible notifications for various events

- [ ] **Create Mailable Class**
    - File: `app/Mail/GenericNotificationMail.php`
    - Copy from: `app/Mail/ExampleMailables.php` → `GenericNotificationMail`

- [ ] **Use Cases**
    - User mentions
    - Thread invitations
    - Bot messages
    - Custom notifications

**Files to Create:**

- [ ] Create: `app/Mail/GenericNotificationMail.php`

---

## 🔧 Implementation Commands

### Create Mailable Classes (Copy Template)

```bash
# Copy the class definitions from ExampleMailables.php to individual files
# After creating, you can delete ExampleMailables.php or keep it for reference
```

### Create Event Listeners

```bash
# Use artisan to generate listener classes
php artisan make:listener SendWelcomeEmail --event=Registered
php artisan make:listener SendFriendRequestEmail --event=FriendRequestEvent
php artisan make:listener SendMessageNotificationEmail --event=NewMessageEvent
php artisan make:listener SendCallNotificationEmail --event=CallStartedEvent
```

---

## 📋 Testing Checklist

For each email you implement:

- [ ] Email renders without errors
- [ ] All variables display correctly
- [ ] Links are correct
- [ ] Mobile responsive
- [ ] Dark mode works
- [ ] No broken images
- [ ] Test in 2+ email clients (Gmail, Outlook, etc.)
- [ ] Links are clickable
- [ ] CTA buttons work

### Test Code Example:

```php
// In tinker or test
Mail::fake();

// Trigger the event
event(new FriendRequestEvent($friend));

// Verify email was sent
Mail::assertSent(FriendRequestMail::class);
```

---

## 📊 Priority Matrix

```
HIGH PRIORITY (Do First):
├── Welcome Email ★★★
│   └── Immediate impact on user experience
├── Friend Request Email ★★★
│   └── Core platform feature
└── Message Notification Email ★★★
    └── Critical for offline users

MEDIUM PRIORITY:
├── Call Notification Email ★★☆
│   └── Important for call feature
├── Security Alert Email ★★☆
│   └── Important for user security
└── Generic Notification Email ★★☆
    └── Used for various features

LOW PRIORITY:
├── Password Reset Email ⭐☆☆
│   └── Already using OTP (better approach)
└── Custom Notification Email ⭐☆☆
    └── Can add later when needed
```

---

## 📈 Completion Progress

### Current: 11% (1/9 Implemented)

```
████░░░░░░░░░░░░░░░░░░░░░░ 1/9
```

### After PHASE 1: 22% (2/9 Implemented)

```
████████░░░░░░░░░░░░░░░░░░ 2/9
```

### After PHASE 2: 33% (3/9 Implemented)

```
████████████░░░░░░░░░░░░░░ 3/9
```

### After PHASE 3: 44% (4/9 Implemented)

```
████████████████░░░░░░░░░░ 4/9
```

### After PHASE 4: 56% (5/9 Implemented)

```
████████████████████░░░░░░ 5/9
```

### After PHASE 5: 67% (6/9 Implemented)

```
████████████████████████░░ 6/9
```

### After PHASE 6: 78% (7/9 Implemented)

```
██████████████████████████░ 7/9
```

---

## 🎯 Quick Actions

### Option 1: Implement One Email (30 minutes)

1. Copy class from `ExampleMailables.php`
2. Create new Mailable file
3. Add trigger in your code
4. Test it works

### Option 2: Implement All (2-3 hours)

1. Create all 6 Mailable classes
2. Create all listeners
3. Register listeners in EventServiceProvider
4. Test each one

### Option 3: Implement Gradually

1. Start with Welcome Email
2. Add one per week
3. Complete by end of month

---

## 📞 Reference Files

- **Full Guide:** `EMAIL_TEMPLATES_GUIDE.md`
- **Quick Reference:** `EMAIL_TEMPLATES_QUICK_REF.md`
- **Examples:** `app/Mail/ExampleMailables.php`
- **Usage Report:** `EMAIL_TEMPLATES_USAGE_REPORT.md` (this document)

---

## ✅ Summary

| Item                 | Status     | Action                  |
| -------------------- | ---------- | ----------------------- |
| Templates            | ✅ Done    | None needed             |
| OTP Mail             | ✅ Done    | None needed             |
| Welcome Mail         | ❌ Pending | Create class & register |
| Friend Request Mail  | ❌ Pending | Create class & listener |
| Message Mail         | ❌ Pending | Create class & listener |
| Call Mail            | ❌ Pending | Create class & listener |
| Security Mail        | ❌ Pending | Create class & trigger  |
| Generic Mail         | ❌ Pending | Create class            |
| Listeners            | ❌ Pending | Create & register       |
| EventServiceProvider | ❌ Pending | Update with listeners   |

**Total Effort:** Low to Medium (2-3 hours for full implementation)  
**Difficulty:** Easy (copy-paste from examples + minimal customization)  
**Recommended Timeline:** 1-2 weeks (do gradually)

---

**Status:** Templates ready for implementation ✅
