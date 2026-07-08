from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.mediciones.models import Medicion, ScriptGEE
from apps.mediciones.importador import importar_csv


@login_required
def index(request):
    mediciones = Medicion.objects.order_by('-fecha')[:50]
    return render(request, 'mediciones/index.html', {'mediciones': mediciones})


@login_required
def importar(request):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para importar datos.')
        return redirect('mediciones:index')

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Debes seleccionar un archivo CSV.')
            return redirect('mediciones:importar')

        if not archivo.name.endswith('.csv'):
            messages.error(request, 'El archivo debe ser un CSV.')
            return redirect('mediciones:importar')

        resultado = importar_csv(archivo, request.user)

        if not resultado['ok']:
            messages.error(request, resultado['error'])
            return redirect('mediciones:importar')

        return render(request, 'mediciones/importar_resultado.html', {
            'resultado': resultado
        })

    # Historial de importaciones
    scripts = ScriptGEE.objects.order_by('-subido_en')[:20]
    return render(request, 'mediciones/importar.html', {'scripts': scripts})

