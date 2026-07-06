from django.urls import path
from .views import (
    trend_chart_realtime,
    TrendChartHistoryView,
    TrendChartThresholdView,
    TrendChartAlarmHistoryView,
)

urlpatterns = [
    path('realtime', trend_chart_realtime, name='trend_chart_realtime'),
    path('history', TrendChartHistoryView.as_view(), name='trend_chart_history'),
    path('threshold', TrendChartThresholdView.as_view(), name='trend_chart_threshold'),
    path('alarm-history', TrendChartAlarmHistoryView.as_view(), name='trend_chart_alarm_history'),
]
