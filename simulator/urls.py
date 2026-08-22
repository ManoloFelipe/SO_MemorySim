from django.urls import path
from . import views

app_name = 'simulator'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/status/', views.api_status, name='api_status'),
    path('api/process/create/', views.api_create_process, name='api_create_process'),
    path('api/process/batch/', views.api_create_batch, name='api_create_batch'),
    path('api/process/<int:pid>/terminate/', views.api_terminate_process, name='api_terminate_process'),
    path('api/simulation/tick/', views.api_tick, name='api_tick'),
    path('api/simulation/toggle/', views.api_toggle_simulation, name='api_toggle_simulation'),
    path('api/simulation/reset/', views.api_reset, name='api_reset'),
]
