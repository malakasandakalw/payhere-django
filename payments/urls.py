from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.plan_list, name='plan-list'),
]
