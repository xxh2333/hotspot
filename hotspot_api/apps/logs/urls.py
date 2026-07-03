from django.urls import path
from .views import OperationLogListView, MaintenanceLogListView

urlpatterns = [
    path('operation', OperationLogListView.as_view(), name='operation_log_list'),
    path('fault', MaintenanceLogListView.as_view(), name='maintenance_log_list'),
]