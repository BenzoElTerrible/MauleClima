from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('consulta-hibrida/', views.consulta_hibrida, name='consulta-hibrida'),
]