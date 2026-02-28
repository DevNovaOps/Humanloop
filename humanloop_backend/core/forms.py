from django import forms
from .models import User


class SignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['name', 'email', 'password', 'role', 'organization']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()


class OTPVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'organization', 'mobile', 'dob']


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data


class PilotForm(forms.Form):
    activity_type = forms.CharField(max_length=50)
    location = forms.CharField(max_length=200)
    date = forms.DateField()
    budget = forms.DecimalField(max_digits=12, decimal_places=2)
    members = forms.IntegerField()
    beneficiaries = forms.IntegerField(required=False)


class FeedbackForm(forms.Form):
    pilot_id = forms.IntegerField(required=False)
    rating = forms.IntegerField(min_value=1, max_value=5)
    message = forms.CharField(widget=forms.Textarea)


class ExpenseForm(forms.Form):
    pilot_id = forms.IntegerField()
    description = forms.CharField(max_length=300)
    amount = forms.DecimalField(max_digits=10, decimal_places=2)
    category = forms.CharField(max_length=30)
