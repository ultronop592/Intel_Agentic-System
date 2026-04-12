from django.urls import path

from competitors import views

app_name = "competitors"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("<int:pk>/", views.competitor_detail, name="detail"),
    path("<int:pk>/delete/", views.delete_competitor, name="delete"),
]
