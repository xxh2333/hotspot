from django.urls import path
from .views import (
    TrendChartRealtimeView,
    TrendChartHistoryView,
    TrendChartThresholdView,
    TrendChartAlarmHistoryView,
)

urlpatterns = [
    path('realtime', TrendChartRealtimeView.as_view(), name='trend_chart_realtime'),
    path('history', TrendChartHistoryView.as_view(), name='trend_chart_history'),
    path('threshold', TrendChartThresholdView.as_view(), name='trend_chart_threshold'),
    path('alarm-history', TrendChartAlarmHistoryView.as_view(), name='trend_chart_alarm_history'),
]
