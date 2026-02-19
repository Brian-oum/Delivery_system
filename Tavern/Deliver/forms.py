from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

# =========================
# Registration Form
# =========================
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")


# =========================
# Custom Login Form
# =========================
class CustomLoginForm(forms.Form):
    username_or_email = forms.CharField(label="Username or Email")
    password = forms.CharField(widget=forms.PasswordInput)
