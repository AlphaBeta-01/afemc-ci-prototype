from django.urls import path

from . import views

app_name = 'membres'

urlpatterns = [
    path('', views.liste, name='liste'),
    path('nouveau/', views.creer, name='creer'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/modifier/', views.modifier, name='modifier'),
]
