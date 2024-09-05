from django import forms
# from django.contrib.auth.models import User
from .models import User
from .models import Profile

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']  # Only include User model fields

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['gender', 'role', 'phone_number', 'address']  # Profile fields