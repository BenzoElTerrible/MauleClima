from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connections
from django.core.paginator import Paginator
from apps.mediciones.models import Medicion, ScriptGEE
from apps.mediciones.importador import importar_csv
from apps.mediciones.forms import MedicionForm
from apps.zonas.models import Zona


def _conteo_por_zona():
    """Aggregation nativa: cuántas mediciones hay por comuna, orden alfabético."""
    coleccion = connections['default'].database['mediciones']
    pipeline = [
        {'$group': {'_id': '$zona_nombre', 'total': {'$sum': 1}}},
        {'$sort': {'_id': 1}},
        {'$limit': 40},
    ]
    return [{'zona': doc['_id'], 'total': doc['total']} for doc in coleccion.aggregate(pipeline)]


@login_required
def index(request):
    zona_id   = request.GET.get('zona', '')
    fuente    = request.GET.get('fuente', '')
    fecha_ini = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    validado  = request.GET.get('validado', '')

    qs = Medicion.objects.order_by('-fecha')

    if zona_id:
        qs = qs.filter(zona_id=zona_id)
    if fuente:
        qs = qs.filter(fuente=fuente)
    if fecha_ini:
        qs = qs.filter(fecha__gte=fecha_ini)
    if fecha_fin:
        qs = qs.filter(fecha__lte=fecha_fin)
    if validado == 'si':
        qs = qs.filter(validado=True)
    elif validado == 'no':
        qs = qs.filter(validado=False)

    paginador = Paginator(qs, 25)
    pagina = paginador.get_page(request.GET.get('pagina'))

    return render(request, 'mediciones/index.html', {
        'pagina':  pagina,
        'resumen': _conteo_por_zona(),
        'zonas':   Zona.objects.order_by('nombre'),
        'filtros': {
            'zona': zona_id, 'fuente': fuente,
            'fecha_inicio': fecha_ini, 'fecha_fin': fecha_fin,
            'validado': validado,
        },
    })


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

    scripts = ScriptGEE.objects.order_by('-subido_en')[:20]
    return render(request, 'mediciones/importar.html', {'scripts': scripts})


@login_required
def crear_medicion(request):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para crear mediciones.')
        return redirect('mediciones:index')

    if request.method == 'POST':
        form = MedicionForm(request.POST)
        if form.is_valid():
            medicion = form.save(commit=False)
            medicion.zona_nombre = medicion.zona.nombre
            medicion.save()
            messages.success(request, 'Medición creada correctamente.')
            return redirect('mediciones:index')
    else:
        form = MedicionForm()

    return render(request, 'mediciones/formulario.html', {
        'form':   form,
        'titulo': 'Nueva medición',
    })


@login_required
def editar_medicion(request, medicion_id):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para editar mediciones.')
        return redirect('mediciones:index')

    medicion = get_object_or_404(Medicion, id=medicion_id)

    if request.method == 'POST':
        form = MedicionForm(request.POST, instance=medicion)
        if form.is_valid():
            medicion = form.save(commit=False)
            medicion.zona_nombre = medicion.zona.nombre
            medicion.save()
            messages.success(request, 'Medición actualizada.')
            return redirect('mediciones:index')
    else:
        form = MedicionForm(instance=medicion)

    return render(request, 'mediciones/formulario.html', {
        'form':   form,
        'titulo': f'Editar medición · {medicion.zona_nombre} ({medicion.fecha})',
    })


@login_required
def eliminar_medicion(request, medicion_id):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para eliminar mediciones.')
        return redirect('mediciones:index')

    medicion = get_object_or_404(Medicion, id=medicion_id)

    if request.method == 'POST':
        medicion.delete()
        messages.success(request, 'Medición eliminada.')
        return redirect('mediciones:index')

    return render(request, 'mediciones/confirmar_eliminar.html', {'medicion': medicion})