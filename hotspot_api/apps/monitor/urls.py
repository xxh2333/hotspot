"""
monitor 实时监控面板 URL 路由
-----------------------------
API 路径严格按照接口文档定义
"""
from django.urls import path
from . import views

urlpatterns = [
    # 仪表盘
    path('dashboard/initial', views.DashboardInitialView.as_view(), name='dashboard_initial'),
    path('dashboard/stream', views.DashboardStreamView.as_view(), name='dashboard_stream'),

    # 温度历史
    path('temperature/history', views.TemperatureHistoryView.as_view(), name='temperature_history'),

    # 告警历史
    path('alarms/history', views.AlarmHistoryView.as_view(), name='alarms_history'),

    # 控制指令
    path('control/reset', views.ControlResetView.as_view(), name='control_reset'),
    path('control/trip', views.ControlTripView.as_view(), name='control_trip'),
    path('control/threshold', views.ControlThresholdView.as_view(), name='control_threshold'),
]
