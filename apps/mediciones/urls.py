from django.urls import path
from . import views

app_name = 'mediciones'

urlpatterns = [
    path('',          views.index,    name='index'),
    path('importar/', views.importar, name='importar'),
]