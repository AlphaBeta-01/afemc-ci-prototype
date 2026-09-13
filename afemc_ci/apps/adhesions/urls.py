from django.urls import path

from . import views

app_name = 'adhesions'

urlpatterns = [
    path('', views.liste, name='liste'),
    path('demande/', views.soumettre, name='soumettre'),
    path('<int:pk>/traiter/', views.traiter, name='traiter'),
    path('pieces/<int:pk>/', views.telecharger_piece, name='telecharger_piece'),
]
