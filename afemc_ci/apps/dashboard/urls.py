from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('a-faire/', views.a_faire, name='a_faire'),
]
