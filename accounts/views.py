from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

# Crear usuario y redirigirlo al dashboard 
def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('/')
        messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'accounts/login.html')

# cierrar sesion
def logout_view(request):
    logout(request)
    return redirect('/accounts/login/')

# crear nuevo uuario y logearlo automaticamente
def registro_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'accounts/registro.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuario ya existe.')
            return render(request, 'accounts/registro.html')
        user = User.objects.create_user(username=username, email=email, password=password1)
        login(request, user)
        return redirect('/')
    return render(request, 'accounts/registro.html')