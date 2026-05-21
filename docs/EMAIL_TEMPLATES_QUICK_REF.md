# Email Templates - Quick Reference

## Brand Color: #008975

## Template Quick Start

### OTP Verification

```php
Mail::send('emails.otp', [
    'user_name' => 'John',
    'otp' => '123456',
    'user_id' => 1,
], function ($m) {
    $m->to('user@example.com')->subject('Verify Your Email');
});
```

### Welcome Email

```php
Mail::send('emails.welcome', [
    'user_name' => 'John',
    'action_url' => route('dashboard'),
], function ($m) {
    $m->to('user@example.com')->subject('Welcome to Hamro Afnai');
});
```

### Friend Request

```php
Mail::send('emails.friend-request', [
    'recipient_name' => 'Jane',
    'sender_name' => 'John Doe',
    'accept_url' => route('friends.accept', ['id' => 1]),
    'decline_url' => route('friends.decline', ['id' => 1]),
], function ($m) {
    $m->to('jane@example.com')->subject('Friend Request from John Doe');
});
```

### Password Reset

```php
Mail::send('emails.password-reset', [
    'user_name' => 'John',
    'reset_url' => route('password.reset', ['token' => $token]),
], function ($m) {
    $m->to('user@example.com')->subject('Reset Your Password');
});
```

### Generic Notification

```php
Mail::send('emails.notification', [
    'title' => 'New Activity',
    'main_message' => 'John liked your post!',
    'action_url' => route('post', ['id' => 1]),
    'action_text' => 'View Post',
], function ($m) {
    $m->to('user@example.com')->subject('New Activity');
});
```

### Message Notification

```php
Mail::send('emails.message-notification', [
    'recipient_name' => 'Jane',
    'sender_name' => 'John',
    'message_preview' => 'Hey Jane!',
    'conversation_url' => route('chat', ['id' => 1]),
], function ($m) {
    $m->to('jane@example.com')->subject('New Message from John');
});
```

### Security Alert

```php
Mail::send('emails.security-alert', [
    'user_name' => 'John',
    'title' => 'Unusual Login',
    'message' => 'New login detected',
    'alert_details' => [
        ['label' => 'Device', 'value' => 'Chrome Windows'],
    ],
    'action_url' => route('security'),
    'action_text' => 'Review',
], function ($m) {
    $m->to('user@example.com')->subject('Security Alert');
});
```

### Call Notification

```php
Mail::send('emails.call-notification', [
    'user_name' => 'Jane',
    'caller_name' => 'John',
    'call_type' => 'Voice Call',
    'answer_url' => route('call.answer', ['id' => 1]),
    'decline_url' => route('call.decline', ['id' => 1]),
], function ($m) {
    $m->to('jane@example.com')->subject('Incoming Call from John');
});
```

### Generic Custom Email

```php
Mail::send('emails.generic', [
    'title' => 'Custom Title',
    'main_content' => '<p>Your content here</p>',
    'action_url' => '#',
    'action_text' => 'Click Me',
], function ($m) {
    $m->to('user@example.com')->subject('Custom Email');
});
```

## Template Files

| Template       | File                                    | Purpose               |
| -------------- | --------------------------------------- | --------------------- |
| OTP            | `emails/otp.blade.php`                  | Account verification  |
| Welcome        | `emails/welcome.blade.php`              | New user onboarding   |
| Friend Request | `emails/friend-request.blade.php`       | Friend requests       |
| Password Reset | `emails/password-reset.blade.php`       | Password reset        |
| Notification   | `emails/notification.blade.php`         | Generic notifications |
| Message        | `emails/message-notification.blade.php` | Message alerts        |
| Security       | `emails/security-alert.blade.php`       | Security alerts       |
| Call           | `emails/call-notification.blade.php`    | Call notifications    |
| Generic        | `emails/generic.blade.php`              | Custom emails         |

## Color Reference

- **Primary Brand Color:** #008975 (Green)
- **Hover/Darker:** #006b5e
- **Success:** #27ae60
- **Warning:** #ffc107
- **Danger:** #e74c3c
- **Info:** #3498db
- **Background:** #f6f7f9
- **Text Dark:** #232b42
- **Text:** #3a4859
- **Text Light:** #667382
- **Border:** #dce0e5

## Common Data Variables (All Templates)

```php
[
    'subject' => 'Email Subject',      // Email subject line
    'preheader' => 'Preview text',     // Text shown in email client preview
    'show_social' => true,             // Show social media links in footer
    'privacy_url' => 'https://...',    // Privacy policy URL
    'terms_url' => 'https://...',      // Terms of service URL
    'unsubscribe_url' => 'https://...', // Unsubscribe URL
]
```

## Styling Classes

### Text

- `.text-center` - Center text
- `.text-muted` - Gray text
- `.text-muted-light` - Lighter gray

### Spacing

- `.mb-0` / `.mb-md` / `.mb-lg` - Bottom margin
- `.mt-md` / `.mt-lg` - Top margin
- `.pt-0` / `.pt-md` / `.pt-lg` - Top padding
- `.pb-md` / `.pb-lg` - Bottom padding

### Components

- `.button` - Primary button (green #008975)
- `.button-secondary` - Secondary button (outline)
- `.badge` - Badge component
- `.highlight` - Highlighted box
- `.divider` - Horizontal line

## Testing

```bash
# View email in browser
php artisan tinker
Mail::send('emails.otp', ['user_name' => 'Test', 'otp' => '123456'], fn($m) => $m->to('test@example.com'))

# Test with fake
Mail::fake();
Mail::to('user@example.com')->send(new OtpMail('123456', 'John', 1));
Mail::assertSent(OtpMail::class);
```

## Layout File

**Location:** `resources/views/layouts/tabler-mail.blade.php`

Extends with sections:

- `@section('content')` - Main email content
- `@section('header_action')` - Top-right header area (badge, status, etc.)
- `@section('footer_content')` - Custom footer content

## Tips

1. Always set `subject` in extends: `@extends('layouts.tabler-mail', ['subject' => '...'])`
2. Use `@section('content')` for main content (wrap in `<tr><td>` tags)
3. Include preheader for better email client preview
4. Use `.highlight` div for important messages
5. Use `.badge` for status indicators
6. Buttons automatically responsive on mobile
7. All colors adapt for dark mode automatically

---

For full documentation, see **EMAIL_TEMPLATES_GUIDE.md**
