"""
URL configuration for hotspot_api project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/log/', include('apps.logs.urls')),
]
