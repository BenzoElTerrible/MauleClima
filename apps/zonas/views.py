from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from apps.zonas.models import Zona
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


@login_required
def index(request):
    # Última fecha disponible por defecto
    ultima = Medicion.objects.order_by('-fecha').first()
    ultima_fecha = str(ultima.fecha) if ultima else ''
    return render(request, 'zonas/index.html', {
        'variables':   VARIABLES,
        'ultima_fecha': ultima_fecha,
    })


@login_required
def geojson(request):
    variable = request.GET.get('variable', 'temperatura_c')
    fecha    = request.GET.get('fecha', '')

    if variable not in VARIABLES:
        variable = 'temperatura_c'

    fuente = VARIABLES[variable]['fuente']

    with open('static/data/maule_comunas.geojson') as f:
        data = json.load(f)

    # Zonas indexadas por codigo_ine
    zonas = {z.codigo_ine: z for z in Zona.objects.all()}

    # Valores de la variable por zona
    qs = Medicion.objects.filter(fuente=fuente)
    if fecha:
        qs = qs.filter(fecha=fecha)

    valores = {}
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
            feature['properties']['nombre']   = zona.nombre
            feature['properties']['valor']    = dato.get('valor')
            feature['properties']['fecha']    = dato.get('fecha')
            feature['properties']['variable'] = variable
            feature['properties']['label']    = VARIABLES[variable]['label']
            feature['properties']['zona_id']  = str(zona.id)
            feature['properties']['provincia'] = zona.provincia.nombre
        else:
            feature['properties']['nombre']   = codigo
            feature['properties']['valor']    = None
            feature['properties']['fecha']    = None

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