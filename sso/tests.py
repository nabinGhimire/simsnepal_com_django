from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from sms.models import SuperBranchUser, SchoolBranch, BranchUser, EduSession
from sms.middleware import _thread_locals

class SSOTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.auto_login_url = reverse('auto_login')
        self.dashboard_url = reverse('dashboard')
        # Ensure default session exists
        self.session_2082, _ = EduSession.objects.get_or_create(year="2082", defaults={"status": True})
        # Clear thread locals before each test
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request

    def tearDown(self):
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request

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

        # Request auto_login with valid token and business_id
        response = self.client.get(self.auto_login_url, {
            'auth_token': 'test_valid_token',
            'business_id': 'business-uuid-111'
        })
        
        # Assert user was redirected to /panel/
        self.assertRedirects(response, '/panel/')

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
        self.client.get(self.auto_login_url, {
            'auth_token': 'test_valid_token',
            'business_id': 'business-uuid-111'
        })

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

        # Assert dashboard access is now blocked (redirects to login which is /?next=...)
        dashboard_response = self.client.get(self.dashboard_url)
        self.assertEqual(dashboard_response.status_code, 302)
        self.assertEqual(dashboard_response.url, '/?next=/dashboard/')

    @patch('requests.get')
    def test_logout_on_new_business_id(self, mock_get):
        # 1. Log in with business-uuid-AAA
        mock_response_aaa = {
            "valid": True,
            "user": {
                "id": 105,
                "username": "sandesh",
                "email": "sandesh@example.com",
                "first_name": "Sandesh",
                "last_name": "Adhikari",
                "hamro_uuid": "user-uuid-999"
            },
            "business_id": "business-uuid-AAA",
            "business_name": "School AAA",
            "module": "students"
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response_aaa

        self.client.get(self.auto_login_url, {
            'auth_token': 'token_aaa',
            'business_id': 'business-uuid-AAA'
        })
        self.assertEqual(self.client.session['sso_business']['id'], 'business-uuid-AAA')

        # 2. Access auto-login with a new business_id 'business-uuid-BBB'
        mock_response_bbb = {
            "valid": True,
            "user": {
                "id": 105,
                "username": "sandesh",
                "email": "sandesh@example.com",
                "first_name": "Sandesh",
                "last_name": "Adhikari",
                "hamro_uuid": "user-uuid-999"
            },
            "business_id": "business-uuid-BBB",
            "business_name": "School BBB",
            "module": "students"
        }
        mock_get.return_value.json.return_value = mock_response_bbb

        response = self.client.get(self.auto_login_url, {
            'auth_token': 'token_bbb',
            'business_id': 'business-uuid-BBB'
        })

        # Assert redirection to /panel/ is still successful
        self.assertRedirects(response, '/panel/')

        # Assert session was updated to the new business ID
        self.assertEqual(self.client.session['sso_business']['id'], 'business-uuid-BBB')
        self.assertEqual(self.client.session['sso_business']['name'], 'School BBB')

    def test_safe_branch_user_multiple_schools_resolution(self):
        # Create a user
        user = self.User.objects.create_user(
            username="multischooluser",
            email="multi@example.com",
            password="testpassword"
        )
        
        # Create a SuperBranchUser to act as added_by
        sbu = SuperBranchUser.objects.create(
            user=user,
            range_start=1000,
            range_end=9999
        )
        
        # Create two different school branches
        school_a = SchoolBranch.objects.create(
            shortcode="school-uuid-A",
            name="School A",
            location="Location A",
            phone=9800000001,
            email="a@school.com",
            owner=sbu,
            status=True,
            min_reg=1000,
            max_reg=9999
        )
        
        school_b = SchoolBranch.objects.create(
            shortcode="school-uuid-B",
            name="School B",
            location="Location B",
            phone=9800000002,
            email="b@school.com",
            owner=sbu,
            status=True,
            min_reg=1000,
            max_reg=9999
        )
        
        # Create two BranchUser records associating user with both schools
        branch_user_a = BranchUser.objects.create(
            school=school_a,
            user=user,
            admin_status=True,
            status=True,
            added_by=sbu
        )
        
        branch_user_b = BranchUser.objects.create(
            school=school_b,
            user=user,
            admin_status=True,
            status=True,
            added_by=sbu
        )
        
        # Verify that direct call to BranchUser.objects.get(user=user)
        # without thread-local session returns one of the active branch users gracefully
        # instead of throwing MultipleObjectsReturned
        res = BranchUser.objects.get(user=user)
        self.assertIn(res, [branch_user_a, branch_user_b])

        # Now mock the request object and set thread-locals
        class MockRequest:
            def __init__(self, session_data):
                self.session = session_data

        # Test resolution for School A
        _thread_locals.request = MockRequest({'sso_business': {'id': 'school-uuid-A'}})
        resolved_a = BranchUser.objects.get(user=user)
        self.assertEqual(resolved_a, branch_user_a)

        # Test resolution for School B
        _thread_locals.request = MockRequest({'sso_business': {'id': 'school-uuid-B'}})
        resolved_b = BranchUser.objects.get(user=user)
        self.assertEqual(resolved_b, branch_user_b)


class AddTeacherTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.session_2082, _ = EduSession.objects.get_or_create(year="2082", defaults={"status": True})
        
        # 1. Create admin user
        self.admin = self.User.objects.create_user(
            username="testadmin",
            email="admin@test.com",
            password="adminpassword"
        )
        self.client.login(username="testadmin", password="adminpassword")
        
        # 2. Create SuperBranchUser
        self.sbu = SuperBranchUser.objects.create(
            user=self.admin,
            range_start=1000,
            range_end=9999
        )
        
        # 3. Create SchoolBranch
        self.school = SchoolBranch.objects.create(
            shortcode="testschool",
            name="Test School",
            location="Kathmandu",
            phone=9800000000,
            email="testschool@school.com",
            owner=self.sbu,
            status=True,
            min_reg=1000,
            max_reg=9999
        )
        
        # 4. Create BranchUser for admin
        self.admin_bu = BranchUser.objects.create(
            school=self.school,
            user=self.admin,
            admin_status=True,
            status=True,
            added_by=self.sbu
        )
        
        # 5. Create Grade, Section, Subject
        from sms.models import GradeLevel, SchoolGrade, Section, Subject
        self.level = GradeLevel.objects.create(name="Secondary Level")
        self.grade = SchoolGrade.objects.create(
            school=self.school,
            grade_name="GRADE 10",
            level=self.level,
            active=True,
            grade_weight=10,
            session=self.session_2082
        )
        self.section = Section.objects.create(
            grade=self.grade,
            section="A",
            session=self.session_2082
        )
        self.subject = Subject.objects.create(
            session=self.session_2082,
            branch=self.school,
            grade=self.grade,
            subject="MATHEMATICS",
            section=self.section
        )

    @patch('requests.post')
    def test_search_iostest_teacher_mock(self, mock_post):
        # Configure mock response to match the contacts/find API payload
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [{
                'contact': 'iostest@hamro.com',
                'found': True,
                'user': {
                    'id': 'mock-uuid-1234',
                    'name': 'IOS Test',
                    'email': 'iostest@hamro.com',
                    'mobile_number': '9801234568',
                    'username': 'ios6230'
                }
            }]
        }
        mock_post.return_value = mock_response

        # Access the view to search for iostest@hamro.com
        url = reverse('add_teacher')
        response = self.client.get(url, {'search_phone': 'iostest@hamro.com'})
        
        # Verify the response is 200 OK and contains mock user details in the context
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['found_user'])
        self.assertEqual(response.context['found_user']['username'], 'ios6230')
        self.assertEqual(response.context['found_user']['first_name'], 'IOS')
        self.assertEqual(response.context['found_user']['last_name'], 'Test')

    def test_register_sso_teacher_creates_branch_user_and_subject_access(self):
        from sms.models import Teacher, TeacherSubjectAccess
        
        # Submit POST request to register the teacher
        url = reverse('add_teacher')
        post_data = {
            'action': 'add_sso_teacher',
            'username': 'iostest@hamro.com',
            'email': 'iostest@hamro.com',
            'first_name': 'IOS',
            'last_name': 'Test'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        
        # Verify User was created
        user_exists = self.User.objects.filter(username='iostest@hamro.com').exists()
        self.assertTrue(user_exists)
        teacher_user = self.User.objects.get(username='iostest@hamro.com')
        
        # Verify Teacher record was created
        teacher_exists = Teacher.objects.filter(teacher=teacher_user).exists()
        self.assertTrue(teacher_exists)
        
        # Verify BranchUser record was created associating teacher with the school branch
        bu_exists = BranchUser.objects.filter(user=teacher_user, school=self.school, status=True).exists()
        self.assertTrue(bu_exists)
        
        # Verify TeacherSubjectAccess was automatically created for mock teacher
        access_exists = TeacherSubjectAccess.objects.filter(
            session=self.session_2082,
            teacher=teacher_user,
            grade=self.grade,
            section=self.section,
            subject=self.subject,
            status=True
        ).exists()
        self.assertTrue(access_exists)



