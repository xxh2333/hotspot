from django.urls import path
from .views import (
    DeviceListView, DeviceDetailView,
    DeviceDataListView, DeviceControlListView,
    MQTTPublishView, MQTTStatusView,
    DeviceSwitchControlView
)

urlpatterns = [
    path('', DeviceListView.as_view(), name='device_list'),
    path('<int:pk>/', DeviceDetailView.as_view(), name='device_detail'),
    path('<int:device_id>/data/', DeviceDataListView.as_view(), name='device_data'),
    path('<int:device_id>/controls/', DeviceControlListView.as_view(), name='device_controls'),
    path('<int:device_id>/switch/', DeviceSwitchControlView.as_view(), name='device_switch'),
    
    path('mqtt/publish/', MQTTPublishView.as_view(), name='mqtt_publish'),
    path('mqtt/status/', MQTTStatusView.as_view(), name='mqtt_status'),
]