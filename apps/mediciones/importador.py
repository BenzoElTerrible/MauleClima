import csv
import io
from datetime import date
from apps.zonas.models import Zona
from apps.mediciones.models import Medicion, ScriptGEE

# Columnas de interés por fuente
ERA5_COLS = {
    'temperatura_c', 'temperatura_min_c', 'temperatura_max_c',
    'total_precipitation_sum', 'u_component_of_wind_10m',
    'v_component_of_wind_10m', 'volumetric_soil_water_layer_1',
    'snow_cover', 'surface_solar_radiation_downwards_sum',
    'dewpoint_temperature_2m',
}
MODIS_COLS = {'NDVI', 'EVI', 'SummaryQA'}


def detectar_fuente(columnas):
    cols = set(columnas)
    if cols & MODIS_COLS:
        return 'MODIS'
    if cols & ERA5_COLS:
        return 'ERA5'
    return None


def importar_csv(archivo, usuario):
    contenido = archivo.read().decode('utf-8')
    reader    = csv.DictReader(io.StringIO(contenido))
    columnas  = reader.fieldnames or []

    # Validación mínima
    if 'nombre' not in columnas or 'fecha' not in columnas:
        return {
            'ok': False,
            'error': 'El archivo debe tener columnas "nombre" y "fecha".'
        }

    fuente = detectar_fuente(columnas)
    if not fuente:
        return {
            'ok': False,
            'error': f'No se reconocen columnas de ERA5 ni MODIS. Columnas encontradas: {", ".join(columnas)}'
        }

    # Cachear zonas por nombre (con y sin tildes)
    zonas = {}
    for z in Zona.objects.all():
        zonas[z.nombre.lower()] = z
        sin_tildes = z.nombre.lower() \
            .replace('á','a').replace('é','e').replace('í','i') \
            .replace('ó','o').replace('ú','u').replace('ñ','n')
        zonas[sin_tildes] = z

    # Crear ScriptGEE
    script = ScriptGEE.objects.create(
        nombre              = archivo.name,
        fuente              = fuente,
        archivo_csv         = archivo.name,
        columnas_detectadas = list(columnas),
        subido_por          = usuario,
    )

    importados = 0
    rechazados = 0
    errores    = []

    for i, row in enumerate(csv.DictReader(io.StringIO(contenido)), start=2):
        nombre    = row.get('nombre', '').strip().lower()
        fecha_str = row.get('fecha',  '').strip()[:10]
        sin_tilde = nombre.replace('á','a').replace('é','e') \
                          .replace('í','i').replace('ó','o') \
                          .replace('ú','u').replace('ñ','n')

        zona = zonas.get(nombre) or zonas.get(sin_tilde)
        if not zona:
            errores.append(f'Fila {i}: comuna "{nombre}" no existe en MongoDB.')
            rechazados += 1
            continue

        try:
            fecha = date.fromisoformat(fecha_str)
        except ValueError:
            errores.append(f'Fila {i}: fecha inválida "{fecha_str}".')
            rechazados += 1
            continue

        def flt(col):
            v = row.get(col, '').strip()
            try:    return float(v) if v else None
            except: return None

        try:
            if fuente == 'ERA5':
                Medicion.objects.create(
                    zona              = zona,
                    zona_nombre       = zona.nombre,
                    fecha             = fecha,
                    fuente            = 'ERA5',
                    temperatura_c     = flt('temperatura_c'),
                    temperatura_min_c = flt('temperatura_min_c'),
                    temperatura_max_c = flt('temperatura_max_c'),
                    precipitacion_mm  = flt('total_precipitation_sum'),
                    viento_u          = flt('u_component_of_wind_10m'),
                    viento_v          = flt('v_component_of_wind_10m'),
                    humedad_suelo     = flt('volumetric_soil_water_layer_1'),
                    cobertura_nieve   = flt('snow_cover'),
                    radiacion_solar   = flt('surface_solar_radiation_downwards_sum'),
                    dewpoint_c        = flt('dewpoint_temperature_2m'),
                    script            = script,
                )
            else:
                ndvi = flt('NDVI')
                evi  = flt('EVI')
                qa   = row.get('SummaryQA', '').strip()
                Medicion.objects.create(
                    zona          = zona,
                    zona_nombre   = zona.nombre,
                    fecha         = fecha,
                    fuente        = 'MODIS',
                    ndvi          = ndvi / 10000 if ndvi else None,
                    evi           = evi  / 10000 if evi  else None,
                    quality_modis = int(qa) if qa.isdigit() else None,
                    script        = script,
                )
            importados += 1
        except Exception as e:
            errores.append(f'Fila {i}: {e}')
            rechazados += 1

    script.registros_importados = importados
    script.registros_rechazados = rechazados
    script.save()

    return {
        'ok':         True,
        'fuente':     fuente,
        'importados': importados,
        'rechazados': rechazados,
        'errores':    errores[:10],
        'script_id':  str(script.id),
    }