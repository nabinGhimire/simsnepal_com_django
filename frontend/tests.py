from django.test import TestCase
from django.urls import reverse
from .models import ContactInquiry

class FrontendPageTests(TestCase):
    def test_home_page_status_code_and_template(self):
        # Assert public home page renders 200 OK and uses correct templates
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/home.html')
        self.assertTemplateUsed(response, 'frontend/base.html')
        self.assertContains(response, "SIMS Nepal")
        self.assertContains(response, "Unifying Academic Excellence")

    def test_features_page_status_code_and_template(self):
        # Assert public features page renders 200 OK and uses correct templates
        response = self.client.get(reverse('features'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/features.html')
        self.assertContains(response, "Engineered System Modules")
        self.assertContains(response, "Academics & Grading")

    def test_pricing_page_status_code_and_template(self):
        # Assert public pricing page renders 200 OK and uses correct templates
        response = self.client.get(reverse('pricing'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/pricing.html')
        self.assertContains(response, "Transparent Modular Pricing")
        self.assertContains(response, "Academy Basic")
        self.assertContains(response, "Standard Core")

    def test_faq_page_status_code_and_template(self):
        # Assert public FAQ page renders 200 OK and uses correct templates
        response = self.client.get(reverse('faq'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/faq.html')
        self.assertContains(response, "Frequently Asked Queries")
        document_text = response.content.decode('utf-8')
        self.assertIn("How does Hamro Business SSO login operate?", document_text)

    def test_about_page_status_code_and_template(self):
        # Assert public about page renders 200 OK and uses correct templates
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/about.html')
        self.assertContains(response, "Our Mission")
        self.assertContains(response, "Our Vision")

    def test_contact_page_status_code_and_template(self):
        # Assert public contact page renders 200 OK and uses correct templates
        response = self.client.get(reverse('contact'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'frontend/contact.html')
        self.assertContains(response, "Connect With Our Team")
        self.assertContains(response, "Send Secure Inquiry")

    def test_home_page_auth_token_redirect(self):
        # Hitting home page with ?auth_token=xyz should redirect to /auto-login/?auth_token=xyz
        token = "token-test-123"
        response = self.client.get(reverse('home'), {'auth_token': token})
        
        # Determine expected redirect path
        expected_redirect_url = f"{reverse('auto_login')}?auth_token={token}"
        self.assertRedirects(response, expected_redirect_url, fetch_redirect_response=False)

    def test_contact_form_submission_success_with_valid_captcha(self):
        # Establish valid CAPTCHA answer in test client session
        session = self.client.session
        session['captcha_answer'] = 15
        session.save()

        post_data = {
            'name': 'Ram Chandra',
            'email': 'ram@edu.np',
            'institution': 'Valley Higher Secondary',
            'message': 'We would like to request an onboarding standard plan.',
            'captcha': '15'
        }

        response = self.client.post(reverse('contact'), post_data)
        self.assertEqual(response.status_code, 200)
        
        # Assert success message is displayed on form template
        self.assertContains(response, "Thank you! Your institutional inquiry was successfully recorded.")
        
        # Assert that the data was successfully saved to persistent backend DB
        self.assertEqual(ContactInquiry.objects.count(), 1)
        inquiry = ContactInquiry.objects.first()
        self.assertEqual(inquiry.name, 'Ram Chandra')
        self.assertEqual(inquiry.institution, 'Valley Higher Secondary')

    def test_contact_form_submission_failure_with_invalid_captcha(self):
        # Establish valid CAPTCHA answer in test client session
        session = self.client.session
        session['captcha_answer'] = 15
        session.save()

        post_data = {
            'name': 'Sita Shrestha',
            'email': 'sita@edu.np',
            'institution': 'Kathmandu Public Academy',
            'message': 'Testing math check system.',
            'captcha': '8'  # Incorrect sum
        }

        response = self.client.post(reverse('contact'), post_data)
        self.assertEqual(response.status_code, 200)
        
        # Assert error message is displayed
        self.assertContains(response, "Incorrect CAPTCHA answer. Please solve the simple math math problem")
        
        # Assert that data was NOT saved to the SQLite inquiries table
        self.assertEqual(ContactInquiry.objects.count(), 0)

    def test_authenticated_user_navigation_elements(self):
        # Create user and authenticate
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user(
            username="navuser", 
            email="nav@example.com", 
            password="testpassword"
        )
        self.client.login(username="navuser", password="testpassword")

        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Assert correct authenticated layout items exist
        self.assertContains(response, "Dashboard Portal")
        self.assertContains(response, "Logout")
        self.assertNotContains(response, "SSO Partner Login")

    def test_anonymous_user_navigation_elements(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Assert anonymous layout items exist
        self.assertContains(response, "SSO Partner Login")
        self.assertContains(response, "Explore Features")
        self.assertNotContains(response, "Logout")

