import os, sys, json, django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.zonas.models import Provincia, Zona

PROVINCIAS = {
    '071': 'Talca',
    '072': 'Cauquenes',
    '073': 'Curicó',
    '074': 'Linares',
}

COMUNAS = {
    # Provincia Talca (071)
    '07101': ('Talca',           '071', -35.4264, -71.6554),
    '07102': ('Constitución',    '071', -35.3333, -72.4167),
    '07103': ('Curepto',         '071', -35.0833, -71.9000),
    '07104': ('Empedrado',       '071', -35.5833, -71.9500),
    '07105': ('Maule',           '071', -35.5000, -71.6667),
    '07106': ('Pelarco',         '071', -35.3333, -71.4167),
    '07107': ('Pencahue',        '071', -35.3833, -71.8000),
    '07108': ('Río Claro',       '071', -35.5333, -71.3833),
    '07109': ('San Clemente',    '071', -35.5333, -71.5000),
    '07110': ('San Rafael',      '071', -35.3667, -71.5000),
    # Provincia Cauquenes (072)
    '07201': ('Cauquenes',       '072', -35.9667, -72.3167),
    '07202': ('Chanco',          '072', -35.7333, -72.5333),
    '07203': ('Pelluhue',        '072', -35.8167, -72.5667),
    # Provincia Curicó (073)
    '07301': ('Curicó',          '073', -34.9822, -71.2397),
    '07302': ('Hualañé',         '073', -34.9833, -71.8167),
    '07303': ('Licantén',        '073', -34.9833, -72.0000),
    '07304': ('Molina',          '073', -35.1167, -71.2833),
    '07305': ('Rauco',           '073', -34.8833, -71.3167),
    '07306': ('Romeral',         '073', -34.7500, -71.0000),
    '07307': ('Sagrada Familia', '073', -34.9667, -71.3833),
    '07308': ('Teno',            '073', -34.8667, -71.1667),
    '07309': ('Vichuquén',       '073', -34.8667, -72.0167),
    # Provincia Linares (074)
    '07401': ('Linares',         '074', -35.8500, -71.5833),
    '07402': ('Colbún',          '074', -35.6833, -71.4333),
    '07403': ('Longaví',         '074', -35.9667, -71.6833),
    '07404': ('Parral',          '074', -36.1500, -71.8333),
    '07405': ('Retiro',          '074', -36.0500, -71.7667),
    '07406': ('San Javier',      '074', -35.5833, -71.7333),
    '07407': ('Villa Alegre',    '074', -35.6667, -71.7500),
    '07408': ('Yerbas Buenas',   '074', -35.7167, -71.5667),
}

def run():
    print("Cargando provincias...")
    provincias_obj = {}
    for cod, nombre in PROVINCIAS.items():
        prov, created = Provincia.objects.get_or_create(nombre=nombre)
        provincias_obj[cod] = prov
        print(f"  {'Creada' if created else 'Existente'}: {nombre}")

    print("\nCargando comunas...")
    for codigo, (nombre, cod_prov, lat, lon) in COMUNAS.items():
        zona, created = Zona.objects.get_or_create(
            nombre=nombre,
            defaults={
                'codigo_ine': codigo,
                'provincia':  provincias_obj[cod_prov],
                'lat':        lat,
                'lon':        lon,
                'cuenca':     'Rio Maule',
            }
        )
        if not zona.codigo_ine:
            zona.codigo_ine = codigo
            zona.save()
        print(f"  {'Creada' if created else 'Existente'}: {nombre} ({codigo})")

    print(f"\nListo. {Provincia.objects.count()} provincias, {Zona.objects.count()} comunas.")

if __name__ == '__main__':
    run()