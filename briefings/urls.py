from django.urls import path

from briefings import views

app_name = "briefings"

urlpatterns = [
    path("", views.briefings_list, name="list"),
    path("<int:pk>/", views.briefing_detail, name="detail"),
]
