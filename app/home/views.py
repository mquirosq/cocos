from django.contrib import messages
from django.shortcuts import redirect, render
from conversion.models import ConversionTask
from .forms import RegistroUsuarioForm

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
