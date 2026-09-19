from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('taches/executer/', views.executer_taches_planifiees, name='executer_taches'),
    path('taches/amorcer-admin/', views.amorcer_administrateur, name='amorcer_administrateur'),
    path('taches/verifier-relance/', views.verifier_relance, name='verifier_relance'),
]
