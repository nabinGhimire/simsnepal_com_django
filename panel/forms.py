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

# Form for updating School information
from sms.models import SchoolBranch

class SchoolForm(forms.ModelForm):
    class Meta:
        model = SchoolBranch
        fields = ['name', 'location', 'phone', 'email', 'logo', 'slogan']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.NumberInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control-file'}),
            'slogan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }