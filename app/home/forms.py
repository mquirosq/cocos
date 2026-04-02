from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
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
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full'}),
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

    def save(self):
        settings_obj, _ = UserNotificationSettings.objects.get_or_create(user=self.user)
        self.user.email = self.cleaned_data['email']
        self.user.save(update_fields=['email'])

        settings_obj.email_notifications_enabled = self.cleaned_data['email_notifications_enabled']
        settings_obj.save(update_fields=['email_notifications_enabled', 'updated_at'])
        return settings_obj
