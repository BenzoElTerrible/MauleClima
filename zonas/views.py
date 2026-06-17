from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from django.http import JsonResponse
from config.db import get_mongo_db, get_neo4j_driver

def consulta_hibrida(request):
    # conexion a neo4j driver y que consulte en cypher vecinos de talca
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (t:Comuna {nombre: 'Talca'})-[:VECINA_DE]->(v)
            RETURN v.zona_id AS zona_id
        """)
        ids_vecinos = [record["zona_id"] for record in result]

    # consultar en mongo, apartir de las id de las zonas anteriores cerca de talca y filtrar estos en que tengan T° superficial mayor a 30°C (lts_dia_c)
    db = get_mongo_db()
    mediciones = db.mediciones.find({
        "zona_id": {"$in": ids_vecinos},
        "lst_dia_c": {"$gt": 30}
    }).limit(10)

    # convertir a lista diccionarios JSON
    data = [{
        "zona_id": m["zona_id"],
        "fecha": m["fecha"],
        "lst_dia_c": m["lst_dia_c"],
        "precip_mm": m["precip_mm"]
    } for m in mediciones]

    return JsonResponse(data, safe=False)
    
@login_required
def dashboard(request):
    return render(request, 'zonas/dashboard.html')