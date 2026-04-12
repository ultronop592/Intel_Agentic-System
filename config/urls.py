from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="landing.html"), name="landing"),
    path("accounts/", include("accounts.urls")),
    path("competitors/", include("competitors.urls")),
    path("briefings/", include("briefings.urls")),
    path("agent/", include("agent.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
