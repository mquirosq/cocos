from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .forms import ProfileSettingsForm, RegistroUsuarioForm

def home(request):
    return render(request, 'home/home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Cuenta creada para {username}. Ya puedes iniciar sesion.')
            return redirect('accounts:login')
    else:
        form = RegistroUsuarioForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile_settings(request):
    if request.method == 'POST':
        form = ProfileSettingsForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile settings updated successfully.')
            return redirect('accounts:profile')
    else:
        form = ProfileSettingsForm(user=request.user)

    return render(request, 'registration/profile.html', {'form': form})
