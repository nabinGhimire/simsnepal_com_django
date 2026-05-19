from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
import json

class SSOTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.auto_login_url = reverse('auto_login')
        self.dashboard_url = reverse('dashboard')

    @patch('requests.get')
    def test_auto_login_success(self, mock_get):
        # Mock successful validation response from business.hamro.com
        mock_response_data = {
            "valid": True,
            "user": {
                "id": 105,
                "username": "sandesh",
                "email": "sandesh@example.com",
                "first_name": "Sandesh",
                "last_name": "Adhikari",
                "full_name": "Sandesh Adhikari",
                "phone": "9841234567",
                "avatar": "https://example.com/avatars/sandesh.jpg",
                "email_verified": True,
                "phone_verified": True,
                "account_verified": True,
                "hamro_uuid": "user-uuid-999"
            },
            "business_id": "business-uuid-111",
            "business_name": "Hamro Secondary School",
            "business": {
                "id": "business-uuid-111",
                "name": "Hamro Secondary School",
                "logo": ""
            },
            "module": "students"
        }
        
        # Configure mock to return 200 OK and JSON data
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response_data

        # Request auto_login with valid token
        response = self.client.get(self.auto_login_url, {'auth_token': 'test_valid_token'})
        
        # Assert user was redirected to dashboard
        self.assertRedirects(response, self.dashboard_url)

        # Assert user was created/updated in the local database
        user_exists = self.User.objects.filter(username="sandesh").exists()
        self.assertTrue(user_exists)
        user = self.User.objects.get(username="sandesh")
        self.assertEqual(user.email, "sandesh@example.com")
        self.assertEqual(user.first_name, "Sandesh")
        self.assertEqual(user.last_name, "Adhikari")

        # Assert session stores SSO user and business details
        session = self.client.session
        self.assertEqual(session['sso_user']['hamro_uuid'], "user-uuid-999")
        self.assertEqual(session['sso_user']['phone'], "9841234567")
        self.assertEqual(session['sso_user']['avatar'], "https://example.com/avatars/sandesh.jpg")
        self.assertEqual(session['sso_business']['id'], "business-uuid-111")
        self.assertEqual(session['sso_business']['name'], "Hamro Secondary School")
        self.assertEqual(session['sso_business']['module'], "students")

    def test_dashboard_fallback_context(self):
        # Create a local user and log them in (simulate local dev access without SSO session)
        user = self.User.objects.create_user(
            username="localuser", 
            email="local@example.com", 
            password="testpassword",
            first_name="Local",
            last_name="User"
        )
        self.client.login(username="localuser", password="testpassword")

        # Access dashboard
        response = self.client.get(self.dashboard_url)
        
        # Assert dashboard renders successfully
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sso/dashboard.html')

        # Assert dashboard context contains fallback data
        context = response.context
        self.assertEqual(context['sso_user']['username'], "localuser")
        self.assertEqual(context['sso_user']['email'], "local@example.com")
        self.assertEqual(context['sso_user']['full_name'], "Local User")
        self.assertEqual(context['sso_business']['id'], "N/A")
        self.assertEqual(context['sso_business']['name'], "Hamro School/Business")

    @patch('requests.get')
    def test_dashboard_with_sso_session(self, mock_get):
        # Log in via auto_login to populate session
        mock_response_data = {
            "valid": True,
            "user": {
                "id": 105,
                "username": "sandesh",
                "email": "sandesh@example.com",
                "first_name": "Sandesh",
                "last_name": "Adhikari",
                "full_name": "Sandesh Adhikari",
                "phone": "9841234567",
                "avatar": "https://example.com/avatars/sandesh.jpg",
                "email_verified": True,
                "phone_verified": True,
                "account_verified": True,
                "hamro_uuid": "user-uuid-999"
            },
            "business_id": "business-uuid-111",
            "business_name": "Hamro Secondary School",
            "business": {
                "id": "business-uuid-111",
                "name": "Hamro Secondary School",
                "logo": ""
            },
            "module": "students"
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response_data

        # Execute SSO login
        self.client.get(self.auto_login_url, {'auth_token': 'test_valid_token'})

        # Access dashboard
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sso/dashboard.html')

        # Assert correct SSO content rendered in page
        self.assertContains(response, "Sandesh Adhikari")
        self.assertContains(response, "Hamro Secondary School")
        self.assertContains(response, "business-uuid-111")
        self.assertContains(response, "students")

    def test_logout_user(self):
        # Create a user and log them in
        self.User.objects.create_user(
            username="logoutuser", 
            email="logout@example.com", 
            password="testpassword"
        )
        self.client.login(username="logoutuser", password="testpassword")

        # Confirm the client is currently logged in
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

        # Execute logout request
        logout_response = self.client.get(reverse('logout'))
        
        # Assert redirect to public home page
        self.assertRedirects(logout_response, reverse('home'))

        # Assert dashboard access is now blocked (redirects to login due to @login_required)
        dashboard_response = self.client.get(self.dashboard_url)
        self.assertEqual(dashboard_response.status_code, 302)
        self.assertIn("login", dashboard_response.url)


