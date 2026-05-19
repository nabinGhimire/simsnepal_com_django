from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


# from snowpenguin.django.recaptcha3.fields import ReCaptchaField

class SignUpForm(UserCreationForm):
    username = forms.CharField(max_length=30, required=True, )
    username.widget.attrs.update({'class': 'form-control', 'placeholder': "Username"})
    first_name = forms.CharField(max_length=30, required=True)
    first_name.widget.attrs.update({'class': 'form-control', 'placeholder': "First Name"})
    last_name = forms.CharField(max_length=30, required=True)
    last_name.widget.attrs.update({'class': 'form-control', 'placeholder': "Last Name"})
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.')
    email.widget.attrs.update({'class': 'form-control', 'placeholder': "Emaill Address"})
    password1 = forms.CharField(max_length=254, widget=forms.PasswordInput)
    password1.widget.attrs.update({'class': 'form-control', 'placeholder': "Password"})

    # captcha = ReCaptchaField()

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['password2']