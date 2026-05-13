from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.add_task, name='add_task'),
    path('delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('voice-config/', views.voice_config_view, name='voice_config'),
    path('api/due-tasks/', views.due_tasks_api, name='due_tasks_api'),
]