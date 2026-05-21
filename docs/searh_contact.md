Admin Integration for External Apps
Scenario Flow
API Integration Steps
Step 1: Search Users in Hamro
Endpoint: POST /api/v1/contacts/find

Response:

Step 2: Store in External App Database
Once admin adds the teacher, external app stores:

Step 3: Later - Teacher Logs In via Webview (Optional)
When the teacher later opens homework via webview:

Response:

Then load webview:

External App Admin Integration Code Example
Search & Add Teacher Flow
Admin UI Flow (React)
Database Schema for External App
Key Points
✅ Search: Use /api/v1/contacts/find to find users by username/email/phone
✅ Store: Save Hamro user_id in external app database
✅ Link: Create mapping between external app school and Hamro user
✅ SSO: Later use stored hamro_user_id for webview authentication
✅ No approval needed: Admin directly adds, user doesn't need to approve