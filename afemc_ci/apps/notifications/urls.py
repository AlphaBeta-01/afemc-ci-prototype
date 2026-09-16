from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.liste, name='liste'),
    path('<int:pk>/renvoyer/', views.renvoyer, name='renvoyer'),
]
