from django.urls import path

from . import views

app_name = 'vitrine'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('page-accueil/modifier/', views.modifier, name='modifier'),
    path('page-accueil/photo-presidente.jpg', views.photo_presidente, name='photo_presidente'),
    path('page-accueil/galerie/<int:pk>.jpg', views.photo_galerie, name='photo_galerie'),
]
