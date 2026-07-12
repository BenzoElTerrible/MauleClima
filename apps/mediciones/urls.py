from django.urls import path
from . import views

app_name = 'mediciones'

urlpatterns = [
    path('',                             views.index,             name='index'),
    path('importar/',                    views.importar,          name='importar'),
    path('crear/',                       views.crear_medicion,    name='crear'),
    path('<str:medicion_id>/editar/',    views.editar_medicion,   name='editar'),
    path('<str:medicion_id>/eliminar/',  views.eliminar_medicion, name='eliminar'),
]