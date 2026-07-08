from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Tu usuario'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Tu contraseña'})
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'correo@utal.cl'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')