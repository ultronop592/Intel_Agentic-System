from django.urls import path

from agent import views

app_name = "agent"

urlpatterns = [
    path("run/<int:pk>/", views.run_agent_view, name="run"),
    path("status/<str:task_id>/", views.agent_status_view, name="status"),
]
