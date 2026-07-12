from django.urls import path
from . import views

app_name = 'zonas'

urlpatterns = [
    path('',                             views.index,          name='index'),
    path('listado/',                     views.listado_zonas,  name='listado'),
    path('crear/',                       views.crear_zona,     name='crear'),
    path('<str:zona_id>/editar/',        views.editar_zona,    name='editar'),
    path('<str:zona_id>/eliminar/',      views.eliminar_zona,  name='eliminar'),
    path('api/geojson/',                 views.geojson,        name='geojson'),
    path('api/serie/<str:zona_id>/',     views.serie_temporal, name='serie'),
    path('api/exportar/<str:zona_id>/',  views.exportar_csv,   name='exportar'),
]