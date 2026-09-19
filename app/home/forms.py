from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from notifications.models import UserNotificationSettings


class RegistroUsuarioForm(UserCreationForm):
    username = forms.CharField(
        label='User',
    )
    password1 = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    error_messages = {
        'password_mismatch': 'The passwords do not match.',
    }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class ProfileSettingsForm(forms.Form):
    email = forms.EmailField(
        required=False,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full'}),
    )
    current_password = forms.CharField(
        required=False,
        label='Current password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full', 'autocomplete': 'current-password'}),
    )
    new_password1 = forms.CharField(
        required=False,
        label='New password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full', 'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        required=False,
        label='Confirm new password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full', 'autocomplete': 'new-password'}),
    )
    email_notifications_enabled = forms.BooleanField(
        required=False,
        label='Enable email notifications',
        widget=forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        if user is None:
            raise ValueError('ProfileSettingsForm requires a user instance.')
        self.user = user
        super().__init__(*args, **kwargs)

        settings_obj, _ = UserNotificationSettings.objects.get_or_create(user=user)
        if not self.is_bound:
            self.initial.setdefault('email', user.email or '')
            self.initial.setdefault('email_notifications_enabled', settings_obj.email_notifications_enabled)

    def clean_new_password1(self):
        new_password1 = self.cleaned_data.get('new_password1')
        if new_password1:
            validate_password(new_password1, user=self.user)
        return new_password1

    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if any([current_password, new_password1, new_password2]):
            if not current_password:
                raise forms.ValidationError('The current password is required to change the password.')

            if not self.user.check_password(current_password):
                raise forms.ValidationError('The current password is incorrect.')

            if not new_password1 or not new_password2:
                raise forms.ValidationError('Please complete both password fields to change your password.')

            if new_password1 != new_password2:
                raise forms.ValidationError('The new passwords do not match.')

            if new_password1 == current_password:
                raise forms.ValidationError('The new password must be different from the current one.')

        if not cleaned_data.get('email') and cleaned_data.get('email_notifications_enabled'):
            raise forms.ValidationError('Email is required to enable email notifications.')

        return cleaned_data

    def save(self):
        settings_obj, _ = UserNotificationSettings.objects.get_or_create(user=self.user)
        self.user.email = self.cleaned_data['email']

        new_password = self.cleaned_data.get('new_password1')
        if new_password:
            self.user.set_password(new_password)

        self.user.save()

        settings_obj.email_notifications_enabled = self.cleaned_data['email_notifications_enabled']
        settings_obj.save(update_fields=['email_notifications_enabled', 'updated_at'])
        return settings_obj
