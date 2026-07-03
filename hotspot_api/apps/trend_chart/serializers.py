from rest_framework import serializers


class TemperatureLogSerializer(serializers.Serializer):
    """温度日志—实时/历史数据序列化"""
    timestamp = serializers.CharField()
    branch = serializers.IntegerField()
    max_temp = serializers.FloatField()
    avg_temp = serializers.FloatField()
    area_ratio = serializers.FloatField()


class HistoryDataPointSerializer(serializers.Serializer):
    """历史曲线数据点序列化"""
    time = serializers.CharField()
    avg_max_temp = serializers.FloatField()
    peak_temp = serializers.FloatField()
    avg_area_ratio = serializers.FloatField()
    max_area_ratio = serializers.FloatField()


class ThresholdSerializer(serializers.Serializer):
    """告警阈值序列化"""
    temp_threshold = serializers.FloatField()
    area_threshold = serializers.FloatField()
    temp_warning_line = serializers.FloatField()
    area_warning_line = serializers.FloatField()
    updated_at = serializers.CharField(allow_null=True)


class AlarmHistorySerializer(serializers.Serializer):
    """故障告警历史序列化"""
    id = serializers.IntegerField()
    timestamp = serializers.CharField()
    alarm_level = serializers.CharField()
    alarm_level_text = serializers.CharField()
    warning_level = serializers.IntegerField(allow_null=True)
    description = serializers.CharField()
    temperature = serializers.FloatField()
    area_ratio = serializers.FloatField()
    threshold_temp = serializers.FloatField(allow_null=True)
    threshold_area = serializers.FloatField(allow_null=True)
    auto_trip = serializers.BooleanField()
    resolution_status = serializers.CharField()
    resolution_status_text = serializers.CharField()
    resolved_at = serializers.CharField(allow_null=True)
