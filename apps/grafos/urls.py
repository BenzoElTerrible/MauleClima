from django.urls import path
from . import views

app_name = 'grafos'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/datos/', views.grafo_data, name='datos'),
    path('api/camino/', views.camino_corto, name='camino'),
    path('api/mas-conectada/', views.mas_conectada, name='mas_conectada'),
    path('api/diagnostico/', views.diagnostico, name='diagnostico'),
    path('api/rankings/', views.rankings, name='rankings'),
    path('api/comunidades/', views.comunidades, name='comunidades'),
    path('api/gds-metricas/', views.gds_metricas, name='gds_metricas'),
    path('consultas/', views.pagina_consultas, name='consultas'),
    path('api/consulta-hibrida/', views.consulta_hibrida, name='consulta_hibrida'),
]