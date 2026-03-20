from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistroUsuarioForm(UserCreationForm):
    username = forms.CharField(
        label='Usuario',
        help_text='Requerido. 150 caracteres o menos. Letras, numeros y @/./+/-/_ solamente.',
    )
    password1 = forms.CharField(
        label='Contrasena',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Usa al menos 8 caracteres y evita claves comunes.',
    )
    password2 = forms.CharField(
        label='Confirmar contrasena',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Escribe la misma contrasena para verificar.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    error_messages = {
        'password_mismatch': 'Las contrasenas no coinciden.',
    }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ese nombre de usuario ya esta registrado.')
        return username
