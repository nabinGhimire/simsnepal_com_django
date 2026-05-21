# Email Templates Guide - Hamro Afnai

This guide explains how to use the updated Tabler email templates in your Laravel application with the custom brand color **#008975**.

## Overview

All email templates now use the professional **Tabler Email Design** with your brand color (#008975) integrated throughout. The templates are:

- ✅ Fully responsive
- ✅ Dark mode compatible
- ✅ Mobile-optimized
- ✅ Built with HTML tables for maximum compatibility
- ✅ Customizable and extensible

## Main Tabler Mail Layout

**Location:** `resources/views/layouts/tabler-mail.blade.php`

This is the base layout extending all email templates. It includes:

- Professional header with logo
- Content wrapper with Tabler styling
- Footer with social links and legal information
- Brand color (#008975) throughout
- Dark mode support via CSS media queries
- Mobile-responsive design

### Using the Layout

```php
@extends('layouts.tabler-mail', [
    'subject' => 'Email Subject',
    'preheader' => 'Preview text visible in email clients',
])
```

## Available Email Templates

### 1. **OTP Email** (`emails/otp.blade.php`)

For account verification and one-time passwords.

**Purpose:** Email verification during registration or sensitive operations

**Data Variables:**

- `user_name` - Name of the recipient (required)
- `otp` - The OTP code to display (required)
- `user_id` - User ID for verification URL
- `verify_url` - Alternative verification URL (or uses route)
- `subject` - Email subject (auto-filled: "Verify Your Email")
- `preheader` - Preview text (auto-filled)

**Example Usage:**

```php
Mail::send('emails.otp', [
    'user_name' => 'John Doe',
    'otp' => '123456',
    'user_id' => $user->id,
    'verify_url' => route('otp.verify', ['user_id' => $user->id])
], function ($m) {
    $m->to('user@example.com')->subject('Verify Your Email');
});
```

---

### 2. **Welcome Email** (`emails/welcome.blade.php`)

For new user onboarding.

**Purpose:** Introduce new users to the platform

**Data Variables:**

- `user_name` - User's name (required)
- `action_url` - URL to start exploring the app
- `help_center_url` - Help center link
- `feedback_url` - Feedback form link

**Example Usage:**

```php
Mail::send('emails.welcome', [
    'user_name' => 'John Doe',
    'action_url' => route('dashboard'),
    'help_center_url' => 'https://hamro.com/help',
], function ($m) {
    $m->to('user@example.com')->subject('Welcome to Hamro Afnai');
});
```

---

### 3. **Friend Request Email** (`emails/friend-request.blade.php`)

For friend request notifications.

**Purpose:** Notify users of incoming friend requests

**Data Variables:**

- `recipient_name` - Name of the person receiving the request (required)
- `sender_name` - Name of the person sending the request (required)
- `sender_avatar_url` - URL to sender's profile picture
- `accept_url` - URL to accept the request (required)
- `decline_url` - URL to decline the request (required)
- `view_profile_url` - URL to view sender's profile
- `settings_url` - URL to privacy settings

**Example Usage:**

```php
Mail::send('emails.friend-request', [
    'recipient_name' => 'Jane',
    'sender_name' => 'John Doe',
    'sender_avatar_url' => $sender->avatar_url,
    'accept_url' => route('friends.accept', ['id' => $request->id]),
    'decline_url' => route('friends.decline', ['id' => $request->id]),
], function ($m) {
    $m->to('jane@example.com')->subject('Friend Request from John Doe');
});
```

---

### 4. **Password Reset Email** (`emails/password-reset.blade.php`)

For password reset requests.

**Purpose:** Allow users to securely reset their password

**Data Variables:**

- `user_name` - User's name (required)
- `reset_url` - Password reset link (required)
- `expiry` - When the link expires (e.g., "24 hours")

**Example Usage:**

```php
Mail::send('emails.password-reset', [
    'user_name' => 'John Doe',
    'reset_url' => route('password.reset', ['token' => $token]),
    'expiry' => '24 hours'
], function ($m) {
    $m->to('user@example.com')->subject('Reset Your Password');
});
```

---

### 5. **Notification Email** (`emails/notification.blade.php`)

Generic, flexible notification template.

**Purpose:** Send various types of notifications

**Data Variables:**

- `title` - Email title (required)
- `icon` - Emoji icon for visual appeal
- `badge_text` - Badge text (e.g., "Notification")
- `greeting` - Opening greeting
- `main_message` - Main notification message (required)
- `details` - Array of detail objects `['label' => 'Label', 'value' => 'Value']`
- `action_url` - Button URL
- `action_text` - Button text
- `additional_content` - HTML content (can include HTML)
- `footer_message` - Additional footer text
- `preferences_url` - Link to notification preferences
- `show_preferences` - Whether to show preferences link

**Example Usage:**

```php
Mail::send('emails.notification', [
    'title' => 'Your Friend John is Now Online',
    'icon' => '👥',
    'badge_text' => 'Friend Activity',
    'main_message' => 'John Doe just came online. Start a conversation!',
    'action_url' => route('chat.open', ['user_id' => $friend->id]),
    'action_text' => 'Open Chat'
], function ($m) {
    $m->to('user@example.com')->subject('Your Friend is Online');
});
```

---

### 6. **Message Notification Email** (`emails/message-notification.blade.php`)

For new message alerts.

**Purpose:** Notify users of incoming messages

**Data Variables:**

- `recipient_name` - Name of recipient (required)
- `sender_name` - Name of the message sender (required)
- `message_preview` - Preview of the message
- `conversation_url` - URL to open the conversation (required)
- `is_group` - Boolean: Is this a group conversation?
- `group_name` - Name of the group (if group message)
- `mute_url` - URL to mute the conversation
- `notification_settings_url` - URL to notification settings

**Example Usage:**

```php
Mail::send('emails.message-notification', [
    'recipient_name' => 'Jane',
    'sender_name' => 'John Doe',
    'message_preview' => 'Hey, how are you doing?',
    'conversation_url' => route('chat.conversation', ['id' => $conversation->id]),
    'is_group' => false
], function ($m) {
    $m->to('jane@example.com')->subject('New Message from John Doe');
});
```

---

### 7. **Security Alert Email** (`emails/security-alert.blade.php`)

For security-related alerts.

**Purpose:** Notify users of security events

**Data Variables:**

- `user_name` - User's name (required)
- `title` - Alert title (required)
- `message` - Alert message (required)
- `alert_details` - Array of alert details `['label' => 'Label', 'value' => 'Value']`
- `action_url` - Action button URL
- `action_text` - Action button text

**Example Usage:**

```php
Mail::send('emails.security-alert', [
    'user_name' => 'John Doe',
    'title' => 'Unusual Login Activity',
    'message' => 'We detected a login to your account from a new device.',
    'alert_details' => [
        ['label' => 'Device', 'value' => 'Chrome on Windows 10'],
        ['label' => 'Location', 'value' => 'Kathmandu, Nepal'],
        ['label' => 'Time', 'value' => now()->format('M d, Y H:i')],
    ],
    'action_url' => route('account.security'),
    'action_text' => 'Review Activity'
], function ($m) {
    $m->to('user@example.com')->subject('Security Alert');
});
```

---

### 8. **Call Notification Email** (`emails/call-notification.blade.php`)

For incoming call alerts.

**Purpose:** Notify users of incoming calls when offline

**Data Variables:**

- `user_name` - User's name (required)
- `caller_name` - Name of the caller (required)
- `caller_avatar_url` - Caller's profile picture URL
- `call_type` - Type of call (e.g., "Voice Call", "Video Call")
- `answer_url` - URL to answer the call
- `decline_url` - URL to decline the call
- `is_group_call` - Boolean: Is this a group call?
- `participants_count` - Number of participants
- `call_time` - Time the call was made
- `disable_call_notifications_url` - URL to disable notifications

**Example Usage:**

```php
Mail::send('emails.call-notification', [
    'user_name' => 'Jane',
    'caller_name' => 'John Doe',
    'caller_avatar_url' => $caller->avatar_url,
    'call_type' => 'Voice Call',
    'answer_url' => route('call.answer', ['id' => $call->id]),
    'decline_url' => route('call.decline', ['id' => $call->id]),
], function ($m) {
    $m->to('jane@example.com')->subject('Incoming Call from John Doe');
});
```

---

### 9. **Generic Template** (`emails/generic.blade.php`)

For custom email types.

**Purpose:** Reusable template for any email type

**Data Variables:**

- `title` - Email title
- `header_icon` - Emoji header icon
- `badge_text` - Badge text
- `show_header_section` - Show header section? (boolean)
- `greeting` - Opening greeting
- `main_content` - Main HTML content
- `action_url` - Primary button URL
- `action_text` - Primary button text
- `action_button_color` - Primary button color (default: #008975)
- `secondary_action_url` - Secondary button URL
- `secondary_action_text` - Secondary button text
- `highlight_content` - Content in highlighted box
- `body_section_items` - Array of section items
- `closing_message` - Closing message
- `footer_links` - Array of footer links `['text' => 'Label', 'url' => 'URL']`
- `footer_message` - Footer message text

**Example Usage:**

```php
Mail::send('emails.generic', [
    'title' => 'Payment Received',
    'header_icon' => '✅',
    'badge_text' => 'Payment',
    'main_content' => '<p>Your payment of $99 has been successfully processed.</p>',
    'body_section_items' => [
        [
            'title' => 'Amount',
            'content' => '$99.00'
        ],
        [
            'title' => 'Transaction ID',
            'content' => '#TXN123456'
        ],
    ],
    'footer_links' => [
        ['text' => 'View Invoice', 'url' => '#'],
        ['text' => 'Download Receipt', 'url' => '#'],
    ],
], function ($m) {
    $m->to('user@example.com')->subject('Payment Received');
});
```

---

## Brand Color Customization

The primary brand color **#008975** is used throughout the templates:

- **Links** - Default link color
- **Buttons** - Primary action buttons
- **Badges** - Highlight badges
- **Highlights** - Highlight boxes and borders
- **Accents** - Various visual accents

### Changing the Brand Color

To change the brand color globally, modify `resources/views/layouts/tabler-mail.blade.php`:

1. Find all instances of `#008975`
2. Replace with your desired color
3. Also update the darker shade for hover states:
    - Original: `#006b5e` (darker version of #008975)
    - Create a darker shade of your new color

**CSS Properties to Update:**

- `a { color: #008975; }` - Links
- `.button { background: #008975; }` - Buttons
- `.button:hover { background: #006b5e; }` - Button hover
- `.badge-success { color: #008975; }` - Success badges
- `.highlight { border-left: 4px solid #008975; }` - Highlights

---

## Creating Custom Mailables

Create a new Mailable class to send emails:

```php
namespace App\Mail;

use Illuminate\Bus\Queueable;
use Illuminate\Mail\Mailable;
use Illuminate\Mail\Mailables\Content;
use Illuminate\Mail\Mailables\Envelope;
use Illuminate\Queue\SerializesModels;

class CustomNotification extends Mailable
{
    use Queueable, SerializesModels;

    public function __construct(
        public string $userName,
        public string $message,
    ) {}

    public function envelope(): Envelope
    {
        return new Envelope(
            subject: 'Custom Notification',
        );
    }

    public function content(): Content
    {
        return new Content(
            view: 'emails.notification',
            with: [
                'title' => 'New Notification',
                'icon' => '🔔',
                'main_message' => $this->message,
                'action_url' => route('dashboard'),
                'action_text' => 'View Details',
            ],
        );
    }
}
```

---

## CSS Classes Available

Use these utility classes in your templates:

### Text Utilities

- `.text-center` - Center text
- `.text-left` - Left align text
- `.text-right` - Right align text
- `.text-muted` - Muted gray color
- `.text-muted-light` - Lighter muted color

### Spacing

- `.mb-0`, `.mb-md`, `.mb-lg` - Margin bottom
- `.mt-md`, `.mt-lg`, `.mt-xl` - Margin top
- `.pt-0`, `.pt-md`, `.pt-lg` - Padding top
- `.pb-0`, `.pb-md`, `.pb-lg` - Padding bottom
- `.px-md`, `.py-lg`, `.py-xl` - Padding utilities

### Layout

- `.va-top`, `.va-middle`, `.va-bottom` - Vertical alignment
- `.w-1p`, `.w-auto` - Width utilities

### Components

- `.badge` - Badge component
- `.badge-success`, `.badge-warning`, `.badge-danger`, `.badge-info` - Badge variants
- `.highlight` - Highlight box
- `.border` - Border
- `.data-table` - Data table styling
- `.button`, `.button-secondary` - Button styles
- `.divider` - Visual divider

---

## Testing Emails

Use Laravel's email preview feature:

```bash
php artisan tinker

// Test OTP email
Mail::send('emails.otp', [
    'user_name' => 'John Doe',
    'otp' => '123456',
    'user_id' => 1
], function ($m) {
    $m->to('test@example.com');
});
```

Or use the Mail::fake() for testing:

```php
Mail::fake();

Mail::to('user@example.com')->send(new OtpMail('123456', 'John Doe', 1));

Mail::assertSent(OtpMail::class);
```

---

## Best Practices

1. **Always include preheader text** - Helps with email client preview
2. **Use descriptive subject lines** - Include action or context
3. **Keep messages concise** - Users scan emails quickly
4. **Include clear CTAs** - Buttons should be obvious
5. **Test across clients** - Different email clients render HTML differently
6. **Use responsive design** - Templates are mobile-optimized
7. **Avoid images as text** - Use text that can be read by screen readers
8. **Test dark mode** - Templates support dark mode automatically

---

## Directory Structure

```
resources/views/
├── layouts/
│   ├── tabler-mail.blade.php    # Main Tabler layout
│   └── mail.blade.php           # Old layout (deprecated)
└── emails/
    ├── otp.blade.php            # OTP verification
    ├── welcome.blade.php        # Welcome email
    ├── friend-request.blade.php # Friend requests
    ├── password-reset.blade.php # Password reset
    ├── notification.blade.php   # Generic notifications
    ├── message-notification.blade.php # Message alerts
    ├── security-alert.blade.php # Security alerts
    ├── call-notification.blade.php # Call alerts
    └── generic.blade.php        # Custom emails
```

---

## Support

For questions or customization needs, please contact support or refer to the [Tabler Emails documentation](https://tabler.io/emails).

---

**Last Updated:** {{ date('F j, Y') }}  
**Brand Color:** #008975 (Hamro Afnai Green)
