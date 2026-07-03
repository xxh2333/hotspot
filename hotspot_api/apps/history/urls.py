from django.urls import path
from .views import HistoryTemperatureViewSet, HistoryAlarmViewSet, TemperatureStreamView

# ── ViewSet → as_view 映射 ──
temperature_list = HistoryTemperatureViewSet.as_view({'get': 'list'})
temperature_export = HistoryTemperatureViewSet.as_view({'post': 'export'})

alarm_list = HistoryAlarmViewSet.as_view({'get': 'list'})
alarm_presign = HistoryAlarmViewSet.as_view({'get': 'presign'})
alarm_export = HistoryAlarmViewSet.as_view({'post': 'export_alarm'})

urlpatterns = [
    # 3.1 历史温度查询
    path('history/temperature/', temperature_list, name='history-temperature-list'),
    # 3.2 温度历史导出
    path('history/temperature/export/', temperature_export, name='history-temperature-export'),
    # 3.6 实时温度 SSE 推送
    path('history/temperature/stream/', TemperatureStreamView.as_view(), name='history-temperature-stream'),
    # 3.3 历史告警查询
    path('history/alarm/', alarm_list, name='history-alarm-list'),
    # 3.4 故障原图预签名URL
    path('history/alarm/<int:pk>/presign/', alarm_presign, name='history-alarm-presign'),
    # 3.5 告警历史导出
    path('history/alarm/export/', alarm_export, name='history-alarm-export'),
]
