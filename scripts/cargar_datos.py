import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pymongo import MongoClient
from neo4j import GraphDatabase

MONGO_URI = 'mongodb://localhost:27017'
NEO4J_URI = 'bolt://localhost:7687'
NEO4J_USER = 'neo4j'
NEO4J_PASSWORD = 'mauleclima2024'

PROVINCIAS = [
    {'provincia_id': 'talca',     'nombre': 'Talca'},
    {'provincia_id': 'curico',    'nombre': 'Curicó'},
    {'provincia_id': 'linares',   'nombre': 'Linares'},
    {'provincia_id': 'cauquenes', 'nombre': 'Cauquenes'},
]

COMUNAS = [
    ('talca',       'talca_01',        'Talca',          -35.4264, -71.6554, 'Rio Maule'),
    ('talca',       'constitucion_01', 'Constitución',   -35.3327, -72.4156, 'Rio Maule'),
    ('talca',       'san_clemente_01', 'San Clemente',   -35.5333, -71.4833, 'Rio Maule'),
    ('talca',       'maule_01',        'Maule',          -35.5065, -71.7054, 'Rio Maule'),
    ('talca',       'pencahue_01',     'Pencahue',       -35.3765, -71.8012, 'Rio Maule'),
    ('curico',      'curico_01',       'Curicó',         -34.9838, -71.2395, 'Rio Teno'),
    ('curico',      'molina_01',       'Molina',         -35.1167, -71.2833, 'Rio Claro'),
    ('curico',      'teno_01',         'Teno',           -34.8667, -71.1667, 'Rio Teno'),
    ('curico',      'hualane_01',      'Hualañé',        -34.9807, -71.8015, 'Rio Mataquito'),
    ('linares',     'linares_01',      'Linares',        -35.8464, -71.5957, 'Rio Achibueno'),
    ('linares',     'parral_01',       'Parral',         -36.1500, -71.8333, 'Rio Loncomilla'),
    ('linares',     'san_javier_01',   'San Javier',     -35.5976, -71.7377, 'Rio Loncomilla'),
    ('linares',     'colbun_01',       'Colbún',         -35.6974, -71.4199, 'Rio Maule'),
    ('cauquenes',   'cauquenes_01',    'Cauquenes',      -35.9667, -72.3167, 'Rio Cauquenes'),
    ('cauquenes',   'chanco_01',       'Chanco',         -35.7333, -72.5333, 'Rio Cauquenes'),
]

VECINDADES = [
    ('talca_01', 'san_clemente_01'),
    ('talca_01', 'maule_01'),
    ('talca_01', 'pencahue_01'),
    ('talca_01', 'constitucion_01'),
    ('curico_01', 'molina_01'),
    ('curico_01', 'teno_01'),
    ('linares_01', 'san_javier_01'),
    ('linares_01', 'colbun_01'),
    ('linares_01', 'parral_01'),
    ('cauquenes_01', 'chanco_01'),
]

import random, datetime
random.seed(42)

def gen_mediciones(zona_id):
    meds = []
    fecha_base = datetime.date(2024, 1, 1)
    for i in range(30):  # 30 dias de datos diarios
        fecha = fecha_base + datetime.timedelta(days=i)
        meds.append({
            'zona_id': zona_id,
            'fecha': fecha.strftime('%Y-%m-%d'),
            'hora': '14:00',
            'fuente': 'MODIS+ERA5',
            'lst_dia_c': round(random.uniform(18, 38), 1),
            'lst_noche_c': round(random.uniform(8, 20), 1),
            'ndvi': round(random.uniform(0.2, 0.7), 3),
            'precip_mm': round(random.uniform(0, 20), 1),
            'humedad_pct': round(random.uniform(30, 80), 1),
        })
    return meds

def main():
    # MongoDB
    client = MongoClient(MONGO_URI)
    db = client['mauleclima']

    db.provincias.drop()
    db.comunas.drop()
    db.mediciones.drop()

    db.provincias.insert_many(PROVINCIAS)
    print(f'✅ {len(PROVINCIAS)} provincias insertadas')

    docs_comunas = []
    for c in COMUNAS:
        docs_comunas.append({
            'provincia_id': c[0],
            'zona_id': c[1],
            'nombre': c[2],
            'lat': c[3],
            'lon': c[4],
            'cuenca': c[5],
        })
    db.comunas.insert_many(docs_comunas)
    print(f'✅ {len(docs_comunas)} comunas insertadas')

    todas_meds = []
    for c in COMUNAS:
        todas_meds.extend(gen_mediciones(c[1]))
    db.mediciones.insert_many(todas_meds)
    print(f'✅ {len(todas_meds)} mediciones diarias insertadas')

    db.comunas.create_index('zona_id', unique=True)
    db.mediciones.create_index([('zona_id', 1), ('fecha', -1)])
    print('✅ Índices creados en MongoDB')

    # Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run('MATCH (n) DETACH DELETE n')

        for p in PROVINCIAS:
            session.run(
                'CREATE (:Provincia {provincia_id: $pid, nombre: $nombre})',
                pid=p['provincia_id'], nombre=p['nombre']
            )
        print(f'✅ {len(PROVINCIAS)} nodos Provincia en Neo4j')

        for c in COMUNAS:
            session.run(
                'CREATE (:Comuna {zona_id: $zid, nombre: $nombre, lat: $lat, lon: $lon, cuenca: $cuenca, provincia_id: $pid})',
                zid=c[1], nombre=c[2], lat=c[3], lon=c[4], cuenca=c[5], pid=c[0]
            )

        for c in COMUNAS:
            session.run('''
                MATCH (p:Provincia {provincia_id: $pid})
                MATCH (c:Comuna {zona_id: $zid})
                CREATE (p)-[:TIENE_COMUNA]->(c)
            ''', pid=c[0], zid=c[1])
        print(f'✅ {len(COMUNAS)} nodos Comuna + relaciones TIENE_COMUNA')

        for origen, destino in VECINDADES:
            session.run('''
                MATCH (a:Comuna {zona_id: $a}), (b:Comuna {zona_id: $b})
                CREATE (a)-[:VECINA_DE]->(b)
                CREATE (b)-[:VECINA_DE]->(a)
            ''', a=origen, b=destino)
        print(f'✅ {len(VECINDADES)*2} relaciones VECINA_DE')

        cuencas = {}
        for c in COMUNAS:
            cuencas.setdefault(c[5], []).append(c[1])
        for cuenca, ids in cuencas.items():
            for i in range(len(ids)):
                for j in range(i+1, len(ids)):
                    session.run('''
                        MATCH (a:Comuna {zona_id: $a}), (b:Comuna {zona_id: $b})
                        CREATE (a)-[:COMPARTE_CUENCA {cuenca: $cuenca}]->(b)
                        CREATE (b)-[:COMPARTE_CUENCA {cuenca: $cuenca}]->(a)
                    ''', a=ids[i], b=ids[j], cuenca=cuenca)
        print('✅ Relaciones COMPARTE_CUENCA creadas')

    driver.close()
    client.close()
    print('\n🎉 Carga completa.')

if __name__ == '__main__':
    main()