from django.urls import path

from . import views

app_name = 'cotisations'

urlpatterns = [
    path('', views.liste, name='liste'),
    path('emettre/', views.emettre, name='emettre'),
    path('<int:pk>/paiement/', views.saisir_paiement, name='paiement'),
    path('export/', views.exporter_csv, name='export'),
]
