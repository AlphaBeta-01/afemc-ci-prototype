from django.urls import path

from . import views

app_name = 'activites'

urlpatterns = [
    path('', views.liste, name='liste'),
    path('nouvelle/', views.creer, name='creer'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/modifier/', views.modifier, name='modifier'),
    path('<int:pk>/statut/', views.statut, name='statut'),
    path('<int:pk>/inscription/', views.inscription, name='inscription'),
    path('<int:pk>/comite/ajouter/', views.comite_ajouter, name='comite_ajouter'),
    path('<int:pk>/comite/<int:comite_pk>/retirer/', views.comite_retirer, name='comite_retirer'),
]
