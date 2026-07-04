from rest_framework import serializers

from apps.logs.models import MaintenanceLog
from .models import TemperatureRecord, AlarmRecord


# ──────────────────────────────────────────────
# 温度历史记录 — 查询序列化器
# ──────────────────────────────────────────────
class TemperatureRecordSerializer(serializers.ModelSerializer):
    """温度历史记录序列化器（列表展示）"""

    timestamp = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%f'[:-3], read_only=True)

    class Meta:
        model = TemperatureRecord
        fields = [
            'id', 'branch', 'timestamp',
            'max_temp', 'min_temp', 'avg_temp',
            'area_ratio', 'hotspot_count',
        ]


# ──────────────────────────────────────────────
# 温度导出 — 请求体校验
# ──────────────────────────────────────────────
class TemperatureExportSerializer(serializers.Serializer):
    """温度历史导出请求体校验"""
    start_time = serializers.DateTimeField(help_text='开始时间（ISO 8601）')
    end_time = serializers.DateTimeField(help_text='结束时间（ISO 8601）')
    branch = serializers.IntegerField(min_value=1, max_value=4, required=False, help_text='支路编号（1~4）')
    min_temp = serializers.FloatField(required=False, allow_null=True, help_text='最低温度筛选')
    max_temp = serializers.FloatField(required=False, allow_null=True, help_text='最高温度筛选')

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError('start_time 必须早于 end_time')
        return attrs


# ──────────────────────────────────────────────
# 告警记录 — 查询序列化器
# ──────────────────────────────────────────────
class MaintenanceInfoSerializer(serializers.Serializer):
    """维修处置记录（嵌套）"""
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    repair_detail = serializers.CharField()
    repair_images = serializers.ListField(child=serializers.CharField())


class AlarmRecordSerializer(serializers.ModelSerializer):
    """告警记录序列化器（列表展示）"""

    trigger_time = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%f'[:-3], read_only=True)
    alarm_type_display = serializers.SerializerMethodField(read_only=True)
    maintenance = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AlarmRecord
        fields = [
            'id', 'branch', 'trigger_time',
            'alarm_type', 'alarm_type_display',
            'warning_level',
            'description',
            'image_path', 'annotated_image_path',
            'temperature', 'temp_difference', 'area_ratio',
            'threshold_temp', 'threshold_area',
            'auto_trip', 'action',
            'resolution_status',
            'resolved_at', 'resolved_by',
            'maintenance',
        ]

    def get_alarm_type_display(self, obj):
        """返回告警类型的中文显示名称"""
        return obj.get_alarm_type_display()

    def get_maintenance(self, obj):
        """
        通过 context 中预加载的 maintenance_map 获取关联的维修记录。
        maintenance_map 在 ViewSet 中批量查询后注入 serializer context，
        避免 N+1 查询。
        """
        maintenance_map = self.context.get('maintenance_map', {})
        m = maintenance_map.get(obj.id)
        if m is None:
            return None
        return {
            'id': m.id,
            'user_id': m.user_id,
            'repair_detail': m.repair_detail,
            'repair_images': m.repair_images or [],
        }


# ──────────────────────────────────────────────
# 告警导出 — 请求体校验
# ──────────────────────────────────────────────
class AlarmExportSerializer(serializers.Serializer):
    """告警历史导出请求体校验"""
    start_time = serializers.DateTimeField(help_text='开始时间（ISO 8601）')
    end_time = serializers.DateTimeField(help_text='结束时间（ISO 8601）')
    branch = serializers.IntegerField(min_value=1, max_value=4, required=False, help_text='支路编号（1~4）')
    alarm_type = serializers.IntegerField(min_value=1, max_value=3, required=False, help_text='告警类型（1/2/3）')
    resolution_status = serializers.ChoiceField(
        choices=['pending', 'resolved', 'recovering'],
        required=False,
        help_text='处置状态',
    )

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError('start_time 必须早于 end_time')
        return attrs
