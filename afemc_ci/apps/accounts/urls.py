from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('connexion/', views.VueConnexion.as_view(), name='connexion'),
    path('deconnexion/', views.VueDeconnexion.as_view(), name='deconnexion'),
    path('activation/<uidb64>/<token>/', views.VueActivation.as_view(), name='activation'),
    path('profil/', views.profil, name='profil'),
    path('responsables/', views.comptes_liste, name='comptes_liste'),
    path('responsables/nouveau/', views.comptes_creer, name='comptes_creer'),
    path('responsables/<int:pk>/basculer/', views.compte_basculer_actif,
         name='compte_basculer_actif'),
]
