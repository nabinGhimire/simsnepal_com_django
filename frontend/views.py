import random
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import ContactInquiry

def home(request):
    """Public home page of SIMS Nepal.
    
    If auth_token query parameter is present, redirect seamlessly
    to the SSO validation flow at auto_login.
    """
    token = request.GET.get('auth_token')
    if token:
        auto_login_url = reverse('auto_login')
        return redirect(f"{auto_login_url}?auth_token={token}")
    return render(request, 'frontend/home.html')

def features(request):
    """Public SEO-friendly features page."""
    return render(request, 'frontend/features.html')

def about(request):
    """Public SEO-friendly about page."""
    return render(request, 'frontend/about.html')

def contact(request):
    """Public SEO-friendly contact page with persistent storage & anti-bot CAPTCHA."""
    success_message = None
    error_message = None
    
    # Store form inputs back on error so users don't have to retype everything
    saved_form_data = {}

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        institution = request.POST.get('institution', '').strip()
        message = request.POST.get('message', '').strip()
        captcha_input = request.POST.get('captcha', '').strip()
        
        saved_form_data = {
            'name': name,
            'email': email,
            'institution': institution,
            'message': message
        }
        
        # Pull correct answer from user's secure session
        correct_answer = request.session.get('captcha_answer')
        
        try:
            if correct_answer is not None and int(captcha_input) == correct_answer:
                # Save to persistent database
                ContactInquiry.objects.create(
                    name=name,
                    email=email,
                    institution=institution,
                    message=message
                )
                success_message = "Thank you! Your institutional inquiry was successfully recorded. We will contact you soon."
                saved_form_data = {}  # Clear input fields on success
                if 'captcha_answer' in request.session:
                    del request.session['captcha_answer']
            else:
                error_message = "Incorrect CAPTCHA answer. Please solve the simple math math problem to verify you are human."
        except (ValueError, TypeError):
            error_message = "Invalid CAPTCHA input. Please type a valid numeric answer."

    # Generate fresh single-digit math query for anti-bot validation
    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    request.session['captcha_answer'] = num1 + num2
    
    context = {
        'num1': num1,
        'num2': num2,
        'success_message': success_message,
        'error_message': error_message,
        'form_data': saved_form_data
    }
    return render(request, 'frontend/contact.html', context)

def pricing(request):
    """Public SEO-friendly plans & pricing page."""
    return render(request, 'frontend/pricing.html')

def faq(request):
    """Public SEO-friendly FAQ page."""
    return render(request, 'frontend/faq.html')
