from django.urls import path
from . import views

urlpatterns = [
    path('ping/', views.response_200, name='response_200'),
    path('app/', views.hello_world, name='hello_world'),
    path('', views.home)
]
