"""
URL configuration for hotspot_api project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def index(request):
    return JsonResponse({
        'message': '光伏热斑检测系统 API',
        'version': '1.0.0',
        'endpoints': [
            {'auth': '/api/auth/login'},
            {'trend-chart': '/api/trend-chart/history'},
            {'logs': '/api/log/operation'},
            {'admin': '/admin/'},
        ]
    })


urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/trend-chart/', include('apps.trend_chart.urls')),
    path('api/log/', include('apps.logs.urls')),
    path('api/', include('apps.history.urls')),
    path('api/', include('apps.monitor.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)