from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import connections
from django.db.models import ProtectedError
from datetime import date, datetime, time
from apps.zonas.models import Zona
from apps.zonas.forms import ZonaForm
from apps.mediciones.models import Medicion
import json

VARIABLES = {
    'temperatura_c':     {'label': 'Temperatura promedio (°C)', 'fuente': 'ERA5'},
    'temperatura_min_c': {'label': 'Temperatura mínima (°C)',   'fuente': 'ERA5'},
    'temperatura_max_c': {'label': 'Temperatura máxima (°C)',   'fuente': 'ERA5'},
    'precipitacion_mm':  {'label': 'Precipitación (mm)',        'fuente': 'ERA5'},
    'humedad_suelo':     {'label': 'Humedad del suelo',         'fuente': 'ERA5'},
    'cobertura_nieve':   {'label': 'Cobertura de nieve',        'fuente': 'ERA5'},
    'ndvi':              {'label': 'NDVI (vegetación)',          'fuente': 'MODIS'},
    'evi':               {'label': 'EVI (vegetación)',           'fuente': 'MODIS'},
}


def _coleccion_mediciones():
    """Coleccion pymongo cruda, sin pasar por el ORM."""
    return connections['default'].database['mediciones']


def _promedios_por_zona(fuente, variable, fecha_inicio, fecha_fin):
    """Aggregation pipeline nativa: $match filtra fuente + rango de fechas,
    $group calcula el promedio ($avg) de la variable por zona."""
    coleccion = _coleccion_mediciones()
    try:
        desde = datetime.combine(date.fromisoformat(fecha_inicio), time.min)
        hasta = datetime.combine(date.fromisoformat(fecha_fin), time.min)
    except ValueError:
        return {}

    pipeline = [
        {'$match': {
            'fuente': fuente,
            'fecha': {'$gte': desde, '$lte': hasta},
            variable: {'$ne': None},
        }},
        {'$group': {
            '_id': '$zona_id',
            'valor': {'$avg': f'${variable}'},
            'n_registros': {'$sum': 1},
        }},
    ]
    return {str(doc['_id']): doc for doc in coleccion.aggregate(pipeline)}


def _conteo_mediciones_por_zona_id():
    """Aggregation nativa: cuántas mediciones tiene cada zona, indexado por su id
    (para mostrar en el listado y advertir antes de intentar eliminar)."""
    coleccion = _coleccion_mediciones()
    pipeline = [
        {'$group': {'_id': '$zona_id', 'total': {'$sum': 1}}},
    ]
    return {str(doc['_id']): doc['total'] for doc in coleccion.aggregate(pipeline)}


@login_required
def index(request):
    ultima = Medicion.objects.order_by('-fecha').first()
    ultima_fecha = str(ultima.fecha) if ultima else ''
    return render(request, 'zonas/index.html', {
        'variables':    VARIABLES,
        'ultima_fecha': ultima_fecha,
    })


@login_required
def geojson(request):
    variable     = request.GET.get('variable', 'temperatura_c')
    fecha        = request.GET.get('fecha', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin    = request.GET.get('fecha_fin', '')

    if variable not in VARIABLES:
        variable = 'temperatura_c'

    fuente = VARIABLES[variable]['fuente']

    with open('static/data/maule_comunas.geojson') as f:
        data = json.load(f)

    zonas = {z.codigo_ine: z for z in Zona.objects.all()}
    valores = {}

    if fecha_inicio and fecha_fin:
        for zona_id, doc in _promedios_por_zona(fuente, variable, fecha_inicio, fecha_fin).items():
            valores[zona_id] = {
                'valor':       round(doc['valor'], 2) if doc['valor'] is not None else None,
                'fecha':       f'{fecha_inicio} a {fecha_fin}',
                'n_registros': doc['n_registros'],
            }
    else:
        qs = Medicion.objects.filter(fuente=fuente)
        if fecha:
            qs = qs.filter(fecha=fecha)
        for m in qs:
            key = str(m.zona_id)
            if key not in valores:
                val = getattr(m, variable, None)
                if val is not None:
                    valores[key] = {'valor': val, 'fecha': str(m.fecha)}

    for feature in data['features']:
        codigo = feature['properties']['codigo_comuna']
        zona   = zonas.get(codigo)
        if zona:
            dato = valores.get(str(zona.id), {})
            feature['properties']['nombre']      = zona.nombre
            feature['properties']['valor']       = dato.get('valor')
            feature['properties']['fecha']       = dato.get('fecha')
            feature['properties']['n_registros'] = dato.get('n_registros')
            feature['properties']['variable']    = variable
            feature['properties']['label']       = VARIABLES[variable]['label']
            feature['properties']['zona_id']     = str(zona.id)
            feature['properties']['provincia']   = zona.provincia.nombre
        else:
            feature['properties']['nombre'] = codigo
            feature['properties']['valor']  = None
            feature['properties']['fecha']  = None

    return JsonResponse(data)


@login_required
def serie_temporal(request, zona_id):
    """Devuelve los últimos 60 días de una variable para una zona."""
    variable = request.GET.get('variable', 'temperatura_c')
    if variable not in VARIABLES:
        variable = 'temperatura_c'

    fuente = VARIABLES[variable]['fuente']

    datos = Medicion.objects.filter(
        zona_id=zona_id,
        fuente=fuente
    ).order_by('fecha').values('fecha', variable)[:60]

    resultado = [
        {'fecha': str(d['fecha']), 'valor': d[variable]}
        for d in datos if d[variable] is not None
    ]
    return JsonResponse({'datos': resultado})


@login_required
def exportar_csv(request, zona_id):
    """Exporta todas las mediciones de una zona como CSV."""
    import csv
    from django.http import HttpResponse

    try:
        zona = Zona.objects.get(id=zona_id)
    except Zona.DoesNotExist:
        return JsonResponse({'error': 'Zona no encontrada'}, status=404)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{zona.nombre}_mediciones.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'zona', 'fecha', 'fuente',
        'temperatura_c', 'temperatura_min_c', 'temperatura_max_c',
        'precipitacion_mm', 'humedad_suelo', 'cobertura_nieve',
        'ndvi', 'evi',
    ])

    for m in Medicion.objects.filter(zona_id=zona_id).order_by('fecha'):
        writer.writerow([
            zona.nombre, m.fecha, m.fuente,
            m.temperatura_c, m.temperatura_min_c, m.temperatura_max_c,
            m.precipitacion_mm, m.humedad_suelo, m.cobertura_nieve,
            m.ndvi, m.evi,
        ])

    return response


@login_required
def listado_zonas(request):
    """Tabla de gestión de comunas — distinta del mapa, que sigue siendo `index`."""
    conteos = _conteo_mediciones_por_zona_id()
    filas = [
        {'zona': z, 'n_mediciones': conteos.get(str(z.id), 0)}
        for z in Zona.objects.order_by('nombre')
    ]
    return render(request, 'zonas/listado.html', {'filas': filas})


@login_required
def crear_zona(request):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para crear comunas.')
        return redirect('zonas:listado')

    if request.method == 'POST':
        form = ZonaForm(request.POST)
        if form.is_valid():
            form.save()
            # TODO: sincronizar con Neo4j cuando se implemente el explorador de grafos
            # (crear el nodo correspondiente a esta comuna nueva)
            messages.success(request, 'Comuna creada correctamente.')
            return redirect('zonas:listado')
    else:
        form = ZonaForm()

    return render(request, 'zonas/formulario.html', {
        'form':   form,
        'titulo': 'Nueva comuna',
    })


@login_required
def editar_zona(request, zona_id):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para editar comunas.')
        return redirect('zonas:listado')

    zona = get_object_or_404(Zona, id=zona_id)

    if request.method == 'POST':
        form = ZonaForm(request.POST, instance=zona)
        if form.is_valid():
            form.save()
            # TODO: sincronizar con Neo4j cuando se implemente el explorador de grafos
            # (actualizar las propiedades del nodo correspondiente)
            messages.success(request, 'Comuna actualizada.')
            return redirect('zonas:listado')
    else:
        form = ZonaForm(instance=zona)

    return render(request, 'zonas/formulario.html', {
        'form':   form,
        'titulo': f'Editar comuna · {zona.nombre}',
    })


@login_required
def eliminar_zona(request, zona_id):
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para eliminar comunas.')
        return redirect('zonas:listado')

    zona = get_object_or_404(Zona, id=zona_id)
    n_mediciones = Medicion.objects.filter(zona=zona).count()

    if request.method == 'POST':
        try:
            zona.delete()
            # TODO: sincronizar con Neo4j cuando se implemente el explorador de grafos
            # (eliminar el nodo correspondiente para no desincronizar ambas bases)
            messages.success(request, f'{zona.nombre} eliminada.')
        except ProtectedError:
            messages.error(
                request,
                f'{zona.nombre} tiene {n_mediciones} mediciones asociadas y no se puede '
                'eliminar mientras existan.'
            )
        return redirect('zonas:listado')

    return render(request, 'zonas/confirmar_eliminar.html', {
        'zona':         zona,
        'n_mediciones': n_mediciones,
    })