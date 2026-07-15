from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from apps.grafos.neo4j_utils import get_driver
from apps.zonas.models import Zona
from apps.mediciones.models import Medicion

TIPOS_RELACION = {
    'vecina': 'VECINA_DE', 'clima': 'CLIMA_SIMILAR',
    'vegetacion': 'VEGETACION_SIMILAR', 'riesgo': 'RIESGO_SIMILAR',
}
PROPIEDAD_POR_TIPO = {
    'vecina': 'distancia_km', 'clima': 'similitud_temp',
    'vegetacion': 'similitud_ndvi', 'riesgo': 'similitud_riesgo',
}
VARIABLES_CONSULTA = {
    'temperatura_max_c': {'label': 'Temperatura máxima (°C)', 'fuente': 'ERA5'},
    'temperatura_c':     {'label': 'Temperatura promedio (°C)', 'fuente': 'ERA5'},
    'precipitacion_mm':  {'label': 'Precipitación (mm)', 'fuente': 'ERA5'},
    'ndvi':              {'label': 'NDVI (vegetación)', 'fuente': 'MODIS'},
}


@login_required
def index(request):
    return render(request, 'grafos/index.html')


@login_required
def grafo_data(request):
    driver = get_driver()
    nodos, aristas = [], []
    with driver.session() as session:
        for r in session.run("MATCH (z:Zona) RETURN z.zona_id AS id, z.nombre AS nombre, z.cuenca AS cuenca"):
            nodos.append({'id': r['id'], 'label': r['nombre'], 'group': 'zona',
                          'title': r['nombre'] + (f" · cuenca {r['cuenca']}" if r['cuenca'] else '')})
        for r in session.run("MATCH (p:Provincia) RETURN p.provincia_id AS id, p.nombre AS nombre"):
            nodos.append({'id': 'prov_' + r['id'], 'label': r['nombre'], 'group': 'provincia'})
        for r in session.run(
            "MATCH (a:Zona)-[rel:VECINA_DE]->(b:Zona) RETURN a.zona_id AS de, b.zona_id AS a_, rel.distancia_km AS d"
        ):
            aristas.append({'from': r['de'], 'to': r['a_'], 'title': f"{r['d']} km", 'tipo': 'vecina'})
        for r in session.run(
            "MATCH (p:Provincia)-[:TIENE_COMUNA]->(z:Zona) RETURN p.provincia_id AS de, z.zona_id AS a_"
        ):
            aristas.append({'from': 'prov_' + r['de'], 'to': r['a_'], 'dashes': True, 'tipo': 'jerarquia'})
        for r in session.run(
            "MATCH (a:Zona)-[rel:CLIMA_SIMILAR]->(b:Zona) RETURN a.zona_id AS de, b.zona_id AS a_, rel.similitud_temp AS s"
        ):
            aristas.append({'from': r['de'], 'to': r['a_'], 'title': f"similitud temp {r['s']}", 'tipo': 'clima'})
        for r in session.run(
            "MATCH (a:Zona)-[rel:VEGETACION_SIMILAR]->(b:Zona) RETURN a.zona_id AS de, b.zona_id AS a_, rel.similitud_ndvi AS s"
        ):
            aristas.append({'from': r['de'], 'to': r['a_'], 'title': f"similitud NDVI {r['s']}", 'tipo': 'vegetacion'})
        for r in session.run(
            "MATCH (a:Zona)-[rel:RIESGO_SIMILAR]->(b:Zona) RETURN a.zona_id AS de, b.zona_id AS a_, rel.similitud_riesgo AS s"
        ):
            aristas.append({'from': r['de'], 'to': r['a_'], 'title': f"similitud riesgo {r['s']}", 'tipo': 'riesgo'})
    return JsonResponse({'nodos': nodos, 'aristas': aristas})


@login_required
def camino_corto(request):
    origen  = request.GET.get('origen', '')
    destino = request.GET.get('destino', '')
    tipo    = request.GET.get('tipo', 'vecina')
    if not origen or not destino:
        return JsonResponse({'error': 'Faltan parametros origen y destino'}, status=400)

    relacion  = TIPOS_RELACION.get(tipo, 'VECINA_DE')
    propiedad = PROPIEDAD_POR_TIPO.get(tipo, 'distancia_km')

    driver = get_driver()
    with driver.session() as session:
        resultado = session.run(
            f"""
            MATCH (o:Zona {{zona_id: $origen}}), (d:Zona {{zona_id: $destino}}),
                  camino = shortestPath((o)-[:{relacion}*]-(d))
            RETURN [n IN nodes(camino) | n.nombre] AS comunas,
                   [r IN relationships(camino) | r.{propiedad}] AS valores,
                   length(camino) AS saltos
            """,
            origen=origen, destino=destino,
        ).single()

    if resultado is None:
        return JsonResponse({'encontrado': False, 'tipo': tipo})
    return JsonResponse({'encontrado': True, 'comunas': resultado['comunas'],
                          'valores': resultado['valores'], 'saltos': resultado['saltos'], 'tipo': tipo})


@login_required
def mas_conectada(request):
    driver = get_driver()
    with driver.session() as session:
        resultado = session.run(
            "MATCH (z:Zona)-[r:VECINA_DE]-() RETURN z.nombre AS nombre, count(r) AS grado "
            "ORDER BY grado DESC LIMIT 1"
        ).single()
    if resultado is None:
        return JsonResponse({})
    return JsonResponse({'nombre': resultado['nombre'], 'grado': resultado['grado']})


@login_required
def diagnostico(request):
    driver = get_driver()
    with driver.session() as session:
        aisladas = [r['nombre'] for r in session.run(
            "MATCH (z:Zona) WHERE NOT (z)-[:VECINA_DE|CLIMA_SIMILAR|VEGETACION_SIMILAR|RIESGO_SIMILAR]-() "
            "RETURN z.nombre AS nombre"
        )]
        sin_clima = [r['nombre'] for r in session.run(
            "MATCH (z:Zona) WHERE NOT (z)-[:CLIMA_SIMILAR]-() RETURN z.nombre AS nombre"
        )]
        total = session.run("MATCH (z:Zona) RETURN count(z) AS n").single()['n']
        conectividad = session.run(
            "MATCH (origen:Zona) WITH origen LIMIT 1 "
            "MATCH (origen)-[:VECINA_DE*]-(alcanzable:Zona) "
            "RETURN count(DISTINCT alcanzable) + 1 AS alcanzables"
        ).single()
        alcanzables = conectividad['alcanzables'] if conectividad else 0

    return JsonResponse({
        'nodos_aislados': aisladas, 'sin_clima_similar': sin_clima,
        'red_totalmente_conectada': alcanzables >= total,
        'alcanzables': alcanzables, 'total_comunas': total,
    })


@login_required
def rankings(request):
    driver = get_driver()
    with driver.session() as session:
        def top(campo, orden='DESC'):
            return [dict(r) for r in session.run(
                f"MATCH (z:Zona) WHERE z.{campo} IS NOT NULL "
                f"RETURN z.nombre AS nombre, z.{campo} AS valor ORDER BY valor {orden} LIMIT 10"
            )]

        precipitacion  = top('precipitacion_promedio')
        amplitud       = top('amplitud_termica_promedio')
        ndvi           = top('ndvi_promedio')
        no_validadas   = [dict(r) for r in session.run(
            "MATCH (z:Zona) WHERE z.n_no_validadas > 0 "
            "RETURN z.nombre AS nombre, z.n_no_validadas AS valor ORDER BY valor DESC LIMIT 10"
        )]
        grado_completo = [dict(r) for r in session.run(
            "MATCH (z:Zona)-[r:VECINA_DE]-() RETURN z.nombre AS nombre, count(r) AS valor ORDER BY valor DESC"
        )]

    return JsonResponse({
        'precipitacion': precipitacion, 'amplitud_termica': amplitud, 'ndvi': ndvi,
        'mas_no_validadas': no_validadas, 'grado_completo': grado_completo,
    })


@login_required
def comunidades(request):
    driver = get_driver()
    try:
        with driver.session() as session:
            session.run("CALL gds.graph.drop('climaGraphComunidades', false)")
            session.run(
                "CALL gds.graph.project("
                "'climaGraphComunidades', 'Zona', "
                "{CLIMA_SIMILAR: {orientation: 'UNDIRECTED', properties: 'similitud_temp'}})"
            )
            resultado = session.run(
                "CALL gds.louvain.stream('climaGraphComunidades', "
                "{relationshipWeightProperty: 'similitud_temp'}) "
                "YIELD nodeId, communityId "
                "RETURN gds.util.asNode(nodeId).nombre AS comuna, communityId "
                "ORDER BY communityId, comuna"
            )
            filas = [{'comuna': r['comuna'], 'comunidad': r['communityId']} for r in resultado]
            session.run("CALL gds.graph.drop('climaGraphComunidades')")
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    grupos = {}
    for fila in filas:
        grupos.setdefault(fila['comunidad'], []).append(fila['comuna'])

    return JsonResponse({'grupos': [
        {'id': cid, 'comunas': sorted(comunas)} for cid, comunas in sorted(grupos.items())
    ]})


@login_required
def gds_metricas(request):
    driver = get_driver()
    resultado = {}
    try:
        with driver.session() as session:
            session.run("CALL gds.graph.drop('gCombinado', false)")
            session.run(
                "CALL gds.graph.project('gCombinado', 'Zona', "
                "{VECINA_DE: {orientation: 'UNDIRECTED'}, CLIMA_SIMILAR: {orientation: 'UNDIRECTED'}})"
            )
            r = session.run(
                "CALL gds.degree.stream('gCombinado') YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).nombre AS comuna, score "
                "ORDER BY score DESC LIMIT 10"
            )
            resultado['grado_combinado'] = [{'comuna': x['comuna'], 'valor': x['score']} for x in r]
            session.run("CALL gds.graph.drop('gCombinado')")

            session.run("CALL gds.graph.drop('gClima', false)")
            session.run(
                "CALL gds.graph.project('gClima', 'Zona', "
                "{CLIMA_SIMILAR: {orientation: 'UNDIRECTED', properties: 'similitud_temp'}})"
            )
            r = session.run(
                "CALL gds.pageRank.stream('gClima', {relationshipWeightProperty: 'similitud_temp'}) "
                "YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).nombre AS comuna, score "
                "ORDER BY score DESC LIMIT 10"
            )
            resultado['pagerank'] = [{'comuna': x['comuna'], 'valor': round(x['score'], 4)} for x in r]
            session.run("CALL gds.graph.drop('gClima')")

            session.run("CALL gds.graph.drop('gVecina', false)")
            session.run(
                "CALL gds.graph.project('gVecina', 'Zona', {VECINA_DE: {orientation: 'UNDIRECTED'}})"
            )
            r = session.run(
                "CALL gds.betweenness.stream('gVecina') YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).nombre AS comuna, score "
                "ORDER BY score DESC LIMIT 10"
            )
            resultado['betweenness'] = [{'comuna': x['comuna'], 'valor': round(x['score'], 2)} for x in r]

            r = session.run(
                "CALL gds.wcc.stream('gVecina') YIELD nodeId, componentId "
                "RETURN componentId, count(*) AS n ORDER BY n DESC"
            )
            resultado['componentes'] = [{'id': x['componentId'], 'n_comunas': x['n']} for x in r]

            r = session.run(
                "CALL gds.nodeSimilarity.stream('gVecina') YIELD node1, node2, similarity "
                "RETURN gds.util.asNode(node1).nombre AS comuna1, "
                "gds.util.asNode(node2).nombre AS comuna2, similarity "
                "ORDER BY similarity DESC LIMIT 10"
            )
            resultado['similares_estructural'] = [
                {'comuna1': x['comuna1'], 'comuna2': x['comuna2'], 'valor': round(x['similarity'], 3)} for x in r
            ]
            session.run("CALL gds.graph.drop('gVecina')")
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse(resultado)


@login_required
def pagina_consultas(request):
    return render(request, 'grafos/consultas.html')


@login_required
def consulta_hibrida(request):
    """Consulta hibrida real: la estructura sale de Neo4j (que comunas
    estan relacionadas con la elegida), el filtro sale de datos reales en MongoDB."""
    zona_base = request.GET.get('zona', '')
    tipo      = request.GET.get('tipo', 'vecina')
    variable  = request.GET.get('variable', 'temperatura_max_c')
    operador  = request.GET.get('operador', 'gt')
    umbral    = request.GET.get('umbral', '')
    fecha_ini = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    if not (zona_base and umbral and fecha_ini and fecha_fin):
        return JsonResponse({'error': 'Completa comuna, umbral y ambas fechas.'}, status=400)

    if variable not in VARIABLES_CONSULTA:
        variable = 'temperatura_max_c'
    try:
        umbral = float(umbral)
    except ValueError:
        return JsonResponse({'error': 'El umbral debe ser un numero.'}, status=400)

    relacion = TIPOS_RELACION.get(tipo, 'VECINA_DE')
    fuente = VARIABLES_CONSULTA[variable]['fuente']

    driver = get_driver()
    with driver.session() as session:
        filas = session.run(
            f"MATCH (o:Zona {{zona_id: $zid}})-[:{relacion}]-(vecina:Zona) "
            f"RETURN DISTINCT vecina.zona_id AS zid, vecina.nombre AS nombre",
            zid=zona_base,
        )
        candidatas = {r['zid']: r['nombre'] for r in filas}
        nombre_base = session.run(
            "MATCH (z:Zona {zona_id: $zid}) RETURN z.nombre AS nombre", zid=zona_base
        ).single()

    nombre_zona_base = nombre_base['nombre'] if nombre_base else zona_base

    if not candidatas:
        return JsonResponse({'zona_base': nombre_zona_base, 'relacion': tipo,
                              'variable': VARIABLES_CONSULTA[variable]['label'], 'resultados': []})

    zonas_mongo = Zona.objects.filter(codigo_ine__in=list(candidatas.keys()))

    filtro = {
        'fuente': fuente,
        'fecha__gte': fecha_ini,
        'fecha__lte': fecha_fin,
        f'{variable}__isnull': False,
    }
    filtro[f'{variable}__gt' if operador == 'gt' else f'{variable}__lt'] = umbral

    resultados = []
    for zona in zonas_mongo:
        coincidencias = Medicion.objects.filter(zona=zona, **filtro).order_by('fecha')
        cantidad = coincidencias.count()
        if cantidad > 0:
            primera = coincidencias.first()
            resultados.append({
                'comuna': zona.nombre,
                'n_coincidencias': cantidad,
                'ejemplo_fecha': str(primera.fecha),
                'ejemplo_valor': getattr(primera, variable),
            })

    return JsonResponse({
        'zona_base': nombre_zona_base,
        'relacion': tipo,
        'variable': VARIABLES_CONSULTA[variable]['label'],
        'resultados': sorted(resultados, key=lambda x: x['n_coincidencias'], reverse=True),
    })