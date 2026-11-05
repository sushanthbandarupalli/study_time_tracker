from django.contrib import admin
from django.urls import include, path
from tracker.views import health

urlpatterns = [path("admin/", admin.site.urls), path("health/", health, name="health"), path("", include("tracker.urls"))]
