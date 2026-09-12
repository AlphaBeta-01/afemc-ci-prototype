from django.urls import path

from . import views

app_name = 'relances'

urlpatterns = [
    path('', views.liste, name='liste'),
]
