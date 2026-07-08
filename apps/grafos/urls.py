from django.urls import path
from . import views

app_name = 'grafos'

urlpatterns = [
    path('', views.index, name='index'),
]