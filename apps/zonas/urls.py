from django.urls import path
from . import views

app_name = 'zonas'

urlpatterns = [
    path('',                          views.index,         name='index'),
    path('api/geojson/',              views.geojson,       name='geojson'),
    path('api/serie/<str:zona_id>/',  views.serie_temporal, name='serie'),
    path('api/exportar/<str:zona_id>/', views.exportar_csv, name='exportar'),
]