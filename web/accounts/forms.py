import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from .models import Role, UserRole
User = get_user_model()


class SignUpForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control", "placeholder": field.label})

    def clean_username(self):
        username = self.cleaned_data["username"]

        if not re.fullmatch(r"[a-zA-Z0-9-]+", username):
         raise forms.ValidationError(
            "Username can only contain letters, numbers, and dashes."
        )

        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
        )
        default_role = Role.objects.get(code="REQUESTER")
        UserRole.objects.create(user=user, role=default_role)
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "placeholder": "Username"})
        self.fields["password"].widget.attrs.update({"class": "form-control", "placeholder": "Password"})