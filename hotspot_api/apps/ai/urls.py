"""
AI + MQTT 接口 URL 路由
"""
from django.urls import path
from .views import (
    ModelInfoView,
    PerformanceMetricsView,
    MqttStatusView,
    MqttMessagesStreamView,
)

urlpatterns = [
    # AI 模型
    path('ai/model-info', ModelInfoView.as_view(), name='ai_model_info'),
    path('ai/metrics', PerformanceMetricsView.as_view(), name='ai_metrics'),

    # MQTT 状态
    path('mqtt/status', MqttStatusView.as_view(), name='mqtt_status'),
    path('mqtt/messages', MqttMessagesStreamView.as_view(), name='mqtt_messages'),
]
