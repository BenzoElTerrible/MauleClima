from math import radians, sin, cos, sqrt, atan2
from django.core.management.base import BaseCommand
from apps.zonas.models import Zona, Provincia
from apps.mediciones.models import Medicion
from apps.grafos.neo4j_utils import get_driver


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def pearson(serie_a, serie_b):
    fechas_comunes = set(serie_a) & set(serie_b)
    if len(fechas_comunes) < 10:
        return None
    xs = [serie_a[f] for f in fechas_comunes]
    ys = [serie_b[f] for f in fechas_comunes]
    n = len(xs)
    media_x = sum(xs) / n
    media_y = sum(ys) / n
    cov   = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    var_x = sum((x - media_x) ** 2 for x in xs)
    var_y = sum((y - media_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / sqrt(var_x * var_y)


def _slug(texto):
    return texto.lower().strip().replace(' ', '_')


def _top_similares(zonas, series, n, zid_fn):
    zonas_con_serie = [z for z in zonas if str(z.id) in series]
    resultado = {}
    for z in zonas_con_serie:
        serie_z = series[str(z.id)]
        correlaciones = []
        for o in zonas_con_serie:
            if o.id == z.id:
                continue
            r = pearson(serie_z, series[str(o.id)])
            if r is not None:
                correlaciones.append((r, o))
        resultado[zid_fn(z)] = sorted(correlaciones, key=lambda item: item[0], reverse=True)[:n]
    return resultado, len(zonas_con_serie)


class Command(BaseCommand):
    help = 'Sincroniza Zonas y Provincias de MongoDB hacia Neo4j (nodos + relaciones + estadisticas).'

    def add_arguments(self, parser):
        parser.add_argument('--vecinos', type=int, default=4)
        parser.add_argument('--similares', type=int, default=3)

    def handle(self, *args, **options):
        n_vecinos   = options['vecinos']
        n_similares = options['similares']
        driver = get_driver()

        zonas      = list(Zona.objects.select_related('provincia').all())
        provincias = list(Provincia.objects.all())

        if not zonas:
            self.stdout.write(self.style.WARNING('No hay zonas en MongoDB. Nada que sincronizar.'))
            return

        def zid(z):
            return z.codigo_ine or _slug(z.nombre)

        series_temp = {}
        series_riesgo = {}
        for d in Medicion.objects.filter(fuente='ERA5').values(
            'zona_id', 'fecha', 'temperatura_c', 'temperatura_max_c'
        ):
            zid_str = str(d['zona_id'])
            if d['temperatura_c'] is not None:
                series_temp.setdefault(zid_str, {})[d['fecha']] = d['temperatura_c']
            if d['temperatura_max_c'] is not None:
                es_extremo = 1 if d['temperatura_max_c'] > 30 else 0
                series_riesgo.setdefault(zid_str, {})[d['fecha']] = es_extremo

        series_ndvi = {}
        for d in Medicion.objects.filter(fuente='MODIS').values('zona_id', 'fecha', 'ndvi'):
            if d['ndvi'] is not None:
                series_ndvi.setdefault(str(d['zona_id']), {})[d['fecha']] = d['ndvi']

        top_clima,  n_con_clima  = _top_similares(zonas, series_temp, n_similares, zid)
        top_veg,    n_con_veg    = _top_similares(zonas, series_ndvi, n_similares, zid)
        top_riesgo, n_con_riesgo = _top_similares(zonas, series_riesgo, n_similares, zid)

        stats_era5 = {}
        for d in Medicion.objects.filter(fuente='ERA5').values(
            'zona_id', 'precipitacion_mm', 'temperatura_max_c', 'temperatura_min_c', 'validado'
        ):
            s = stats_era5.setdefault(str(d['zona_id']), {'precip': [], 'amplitud': [], 'n': 0, 'n_no_validado': 0})
            s['n'] += 1
            if not d['validado']:
                s['n_no_validado'] += 1
            if d['precipitacion_mm'] is not None:
                s['precip'].append(d['precipitacion_mm'])
            if d['temperatura_max_c'] is not None and d['temperatura_min_c'] is not None:
                s['amplitud'].append(d['temperatura_max_c'] - d['temperatura_min_c'])

        stats_modis = {}
        for d in Medicion.objects.filter(fuente='MODIS').values('zona_id', 'ndvi'):
            s = stats_modis.setdefault(str(d['zona_id']), {'ndvi': [], 'n': 0})
            s['n'] += 1
            if d['ndvi'] is not None:
                s['ndvi'].append(d['ndvi'])

        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

            for prov in provincias:
                session.run(
                    "MERGE (p:Provincia {provincia_id: $pid}) SET p.nombre = $nombre",
                    pid=_slug(prov.nombre), nombre=prov.nombre,
                )

            for z in zonas:
                zid_str = str(z.id)
                e = stats_era5.get(zid_str, {'precip': [], 'amplitud': [], 'n': 0, 'n_no_validado': 0})
                m = stats_modis.get(zid_str, {'ndvi': [], 'n': 0})
                session.run(
                    """
                    MERGE (n:Zona {zona_id: $zid})
                    SET n.nombre = $nombre, n.lat = $lat, n.lon = $lon, n.cuenca = $cuenca,
                        n.precipitacion_promedio = $precip_prom,
                        n.amplitud_termica_promedio = $amplitud_prom,
                        n.ndvi_promedio = $ndvi_prom,
                        n.n_mediciones_era5 = $n_era5,
                        n.n_mediciones_modis = $n_modis,
                        n.n_no_validadas = $n_no_validado
                    """,
                    zid=zid(z), nombre=z.nombre, lat=z.lat, lon=z.lon, cuenca=z.cuenca or '',
                    precip_prom=round(sum(e['precip']) / len(e['precip']), 2) if e['precip'] else None,
                    amplitud_prom=round(sum(e['amplitud']) / len(e['amplitud']), 2) if e['amplitud'] else None,
                    ndvi_prom=round(sum(m['ndvi']) / len(m['ndvi']), 4) if m['ndvi'] else None,
                    n_era5=e['n'], n_modis=m['n'], n_no_validado=e['n_no_validado'],
                )

            for z in zonas:
                session.run(
                    """
                    MATCH (p:Provincia {provincia_id: $pid}), (n:Zona {zona_id: $zid})
                    MERGE (p)-[:TIENE_COMUNA]->(n)
                    """,
                    pid=_slug(z.provincia.nombre), zid=zid(z),
                )

            for z in zonas:
                cercanas = sorted(
                    ((haversine_km(z.lat, z.lon, o.lat, o.lon), o) for o in zonas if o.id != z.id),
                    key=lambda item: item[0],
                )[:n_vecinos]
                for dist, otra in cercanas:
                    session.run(
                        """
                        MATCH (a:Zona {zona_id: $a}), (b:Zona {zona_id: $b})
                        MERGE (a)-[r:VECINA_DE]->(b)
                        SET r.distancia_km = $d
                        """,
                        a=zid(z), b=zid(otra), d=round(dist, 1),
                    )

            for zona_id_a, similares in top_clima.items():
                for r, otra in similares:
                    session.run(
                        "MATCH (a:Zona {zona_id: $a}), (b:Zona {zona_id: $b}) "
                        "MERGE (a)-[rel:CLIMA_SIMILAR]->(b) SET rel.similitud_temp = $r",
                        a=zona_id_a, b=zid(otra), r=round(r, 3),
                    )

            for zona_id_a, similares in top_veg.items():
                for r, otra in similares:
                    session.run(
                        "MATCH (a:Zona {zona_id: $a}), (b:Zona {zona_id: $b}) "
                        "MERGE (a)-[rel:VEGETACION_SIMILAR]->(b) SET rel.similitud_ndvi = $r",
                        a=zona_id_a, b=zid(otra), r=round(r, 3),
                    )

            for zona_id_a, similares in top_riesgo.items():
                for r, otra in similares:
                    session.run(
                        "MATCH (a:Zona {zona_id: $a}), (b:Zona {zona_id: $b}) "
                        "MERGE (a)-[rel:RIESGO_SIMILAR]->(b) SET rel.similitud_riesgo = $r",
                        a=zona_id_a, b=zid(otra), r=round(r, 3),
                    )

        self.stdout.write(self.style.SUCCESS(
            f'Sincronizadas {len(zonas)} zonas y {len(provincias)} provincias a Neo4j. '
            f'{n_con_clima} con clima similar, {n_con_veg} con vegetacion similar, '
            f'{n_con_riesgo} con riesgo similar.'
        ))