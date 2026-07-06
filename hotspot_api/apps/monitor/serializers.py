from rest_framework import serializers
from .models import (
    BranchStatus, TemperatureRecord, AlarmRecord,
    SystemConfig, DeviceStatus, ThermalImage,
)


# ---------------------------------------------------------------------------
# 统一响应包装
# ---------------------------------------------------------------------------

class APIResponse:
    """统一响应格式工厂"""
    @staticmethod
    def ok(data=None, msg='success', trace_id=None):
        import uuid
        return {
            'code': 0,
            'msg': msg,
            'data': data,
            'success': True,
            'trace_id': trace_id or str(uuid.uuid4()),
        }

    @staticmethod
    def fail(code, msg, data=None):
        import uuid
        return {
            'code': code,
            'msg': msg,
            'data': data,
            'success': False,
            'trace_id': str(uuid.uuid4()),
        }


# ---------------------------------------------------------------------------
# 支路状态
# ---------------------------------------------------------------------------

class BranchStatusSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='branch')

    class Meta:
        model = BranchStatus
        fields = ['id', 'temperature', 'area_ratio', 'breaker_status', 'alarm_status', 'updated_at']


class BranchStatusSimpleSerializer(serializers.Serializer):
    """SSE 推送用的精简版支路状态"""
    id = serializers.IntegerField()
    temperature = serializers.FloatField()
    area_ratio = serializers.FloatField()
    breaker_status = serializers.CharField()
    alarm_status = serializers.CharField()


# ---------------------------------------------------------------------------
# 全局温度统计
# ---------------------------------------------------------------------------

class GlobalTempSerializer(serializers.Serializer):
    max_temp = serializers.FloatField()
    min_temp = serializers.FloatField()
    avg_temp = serializers.FloatField()
    max_temp_branch = serializers.IntegerField()
    min_temp_branch = serializers.IntegerField()


# ---------------------------------------------------------------------------
# 告警统计
# ---------------------------------------------------------------------------

class AlarmBreakdownSerializer(serializers.Serializer):
    hot_spot = serializers.IntegerField()
    over_temp = serializers.IntegerField()
    offline = serializers.IntegerField()


class AlarmStatisticsSerializer(serializers.Serializer):
    date = serializers.CharField()
    total = serializers.IntegerField()
    breakdown = AlarmBreakdownSerializer()
    unresolved = serializers.IntegerField()


# ---------------------------------------------------------------------------
# 设备/相机/MQTT 状态
# ---------------------------------------------------------------------------

class DeviceInfoSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    online = serializers.IntegerField()
    offline_list = serializers.ListField(child=serializers.CharField())


class ThermalCameraSerializer(serializers.Serializer):
    status = serializers.CharField()
    fps = serializers.FloatField()


class MqttStatusSerializer(serializers.Serializer):
    status = serializers.CharField()


# ---------------------------------------------------------------------------
# 阈值
# ---------------------------------------------------------------------------

class ThresholdSerializer(serializers.Serializer):
    temperature = serializers.FloatField()
    area_ratio = serializers.FloatField()


# ---------------------------------------------------------------------------
# 仪表盘初始数据（聚合响应）
# ---------------------------------------------------------------------------

class DashboardInitialSerializer(serializers.Serializer):
    timestamp = serializers.CharField()
    branches = BranchStatusSerializer(many=True)
    global_stats = GlobalTempSerializer(source='global')
    alarm_statistics = AlarmStatisticsSerializer()
    devices = DeviceInfoSerializer()
    thermal_camera = ThermalCameraSerializer()
    mqtt = MqttStatusSerializer()
    thresholds = ThresholdSerializer()


# ---------------------------------------------------------------------------
# 温度历史
# ---------------------------------------------------------------------------

class TemperatureHistoryRequestSerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1, max_value=4)
    start = serializers.CharField()
    end = serializers.CharField()
    interval = serializers.ChoiceField(choices=['hour', 'day'], default='hour', required=False)


class TemperatureSeriesItemSerializer(serializers.Serializer):
    time = serializers.CharField()
    max_temp = serializers.FloatField()
    avg_temp = serializers.FloatField()


class TemperatureHistoryResponseSerializer(serializers.Serializer):
    branch = serializers.IntegerField()
    start = serializers.CharField()
    end = serializers.CharField()
    interval = serializers.CharField()
    series = TemperatureSeriesItemSerializer(many=True)


# ---------------------------------------------------------------------------
# 告警历史
# ---------------------------------------------------------------------------

class AlarmRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlarmRecord
        fields = [
            'id', 'timestamp', 'branch', 'alarm_type', 'temperature',
            'area_ratio', 'status', 'image_path',
        ]


class AlarmHistoryResponseSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    page = serializers.IntegerField()
    limit = serializers.IntegerField()
    list = AlarmRecordSerializer(many=True)


# ---------------------------------------------------------------------------
# 控制指令
# ---------------------------------------------------------------------------

class ControlResetSerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1, max_value=4)
    operator = serializers.CharField(max_length=64, default='admin')


class ControlTripSerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1, max_value=4)
    operator = serializers.CharField(max_length=64, default='admin')
    reason = serializers.CharField(max_length=256, default='人工远程分闸', required=False)


class ControlResultSerializer(serializers.Serializer):
    branch = serializers.IntegerField()
    command = serializers.CharField()
    status = serializers.CharField()


class ThresholdUpdateSerializer(serializers.Serializer):
    temperature = serializers.FloatField(min_value=30.0, max_value=120.0)
    area_ratio = serializers.FloatField(min_value=1.0, max_value=30.0)


class ThresholdResultSerializer(serializers.Serializer):
    temperature = serializers.FloatField()
    area_ratio = serializers.FloatField()
    effective_at = serializers.CharField()


# ---------------------------------------------------------------------------
# SSE 事件数据
# ---------------------------------------------------------------------------

class SSEStatusDataSerializer(serializers.Serializer):
    """SSE status 事件数据结构"""
    timestamp = serializers.CharField()
    branches = BranchStatusSimpleSerializer(many=True)
    global_stats = GlobalTempSerializer(source='global')
    devices = serializers.DictField()


class SSEAlarmDataSerializer(serializers.Serializer):
    """SSE alarm 事件数据结构"""
    timestamp = serializers.CharField()
    alarm_id = serializers.IntegerField()
    branch = serializers.IntegerField()
    alarm_type = serializers.CharField()
    temperature = serializers.FloatField()
    area_ratio = serializers.FloatField()
    auto_trip = serializers.BooleanField()
    image_path = serializers.CharField()
    description = serializers.CharField()


class SSEImageDataSerializer(serializers.Serializer):
    """SSE image 事件数据结构"""
    timestamp = serializers.CharField()
    image = serializers.CharField()
    annotated = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()
