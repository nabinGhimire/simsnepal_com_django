# SIMS Webview Integration Guide

This document outlines the API and integration steps for the **Hamro Ecosystem (Laravel Backend)** to securely generate and embed webviews for the **SIMS** platform. 

The webviews allow Parents to view homework/results and Teachers to enter bulk homework/marks directly from the mobile app without requiring a separate password login.

---

## 1. Token Generation API (Server-to-Server)

To ensure maximum security, the SIMS platform does NOT accept raw UUIDs or phone numbers in the webview URL. Instead, the Laravel backend must request a time-limited **Cryptographic Token** from SIMS before rendering the webview.

**Endpoint:** `POST https://simsnepal.com/webview/api/auth-token/`

### Required Headers
You must authenticate the Server-to-Server request using the shared secret key.
```http
X-API-Key: hamro-sims-secure-api-key-2026
```

### Request Payload (JSON)
You can send the parent's phone number, the teacher's UUID, or both.
```json
{
  "phone": "9801234567",
  "hamro_uuid": "user_uuid_from_hamro"
}
```

### Response Payload
SIMS will check its database. If the phone is tied to a student's parent, it returns a `parent_token`. If the UUID is tied to an active teacher, it returns a `teacher_token`.

```json
{
  "exists": true,
  "roles": ["parent", "teacher"],
  "parent_token": "9801234567:1pGZ_...signature_string",
  "teacher_token": "user_id:1pGZ_...signature_string"
}
```
> [!IMPORTANT]
> - These tokens expire automatically after **24 hours**.
> - Always generate a fresh token when the user opens the webview page in the app.

---

## 2. Webview Endpoints

Once you have the token, you can construct the webview URL and load it in the mobile app's in-app browser (WebView).

### Parent Webviews
Use the `parent_token` returned by the API.

- **Daily Homework:**  
  `https://simsnepal.com/webview/parent/homework/?token={parent_token}`

- **Exam Results:**  
  `https://simsnepal.com/webview/parent/result/?token={parent_token}`

### Teacher Webviews
Use the `teacher_token` returned by the API.

- **Bulk Homework Entry:**  
  `https://simsnepal.com/webview/teacher/homework/?token={teacher_token}`  
  *(Note: This interface has been optimized to list ALL of the teacher's assigned subjects across all classes/schools in a single form!)*

- **Marks Entry Links:**  
  `https://simsnepal.com/webview/teacher/marks/?token={teacher_token}`

---

## 3. Error Handling

If a token is missing, expired, or invalid, the webview will automatically render a clean, branded Error Page (`error.html`) stating **Unauthorized Access**. 

If you receive complaints from users seeing this screen, ensure your Laravel backend is requesting a fresh token every time the webview is opened rather than caching it on the device indefinitely.
