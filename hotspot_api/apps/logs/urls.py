from django.urls import path
from .views import (
    OperationLogListView,
    OperationLogCreateView,
    MaintenanceLogListView,
    MaintenanceLogCreateView,
    ImageUploadView,
)

urlpatterns = [
    path('operation', OperationLogListView.as_view(), name='operation_log_list'),
    path('operation/create', OperationLogCreateView.as_view(), name='operation_log_create'),
    path('fault', MaintenanceLogListView.as_view(), name='maintenance_log_list'),
    path('fault/create', MaintenanceLogCreateView.as_view(), name='maintenance_log_create'),
    path('upload-image', ImageUploadView.as_view(), name='image_upload'),
]
