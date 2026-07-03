from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import OperationLog, MaintenanceLog, AlarmLog

User = get_user_model()


class OperationLogSerializer(serializers.ModelSerializer):
    """
    人员操作日志序列化器
    """
    operator_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OperationLog
        fields = ['id', 'operator_name', 'branch', 'action_type', 'is_success', 'action_detail', 'created_at']

    def get_operator_name(self, obj):
        """
        通过 user_id 关联获取用户名
        """
        try:
            user = User.objects.get(id=obj.user_id)
            return user.nickname or user.username
        except User.DoesNotExist:
            return '未知用户'


class MaintenanceLogSerializer(serializers.ModelSerializer):
    """
    故障处置日志序列化器
    """
    fault_date = serializers.SerializerMethodField(read_only=True)
    fault_time = serializers.SerializerMethodField(read_only=True)
    device_code = serializers.SerializerMethodField(read_only=True)
    images = serializers.JSONField(source='repair_images', read_only=True)
    repairer_name = serializers.SerializerMethodField(read_only=True)
    remark = serializers.CharField(source='repair_detail', read_only=True)

    class Meta:
        model = MaintenanceLog
        fields = ['id', 'fault_date', 'fault_time', 'fault_device', 'device_code', 'images', 'repairer_name', 'remark']

    def get_fault_date(self, obj):
        """
        获取 created_at 的日期部分
        """
        return obj.created_at.date() if obj.created_at else None

    def get_fault_time(self, obj):
        """
        获取 created_at 的时间部分
        """
        return obj.created_at.time() if obj.created_at else None

    def get_device_code(self, obj):
        """
        通过关联告警获取支路编号
        """
        try:
            alarm = AlarmLog.objects.get(id=obj.alarm_id)
            return alarm.branch
        except AlarmLog.DoesNotExist:
            return None

    def get_repairer_name(self, obj):
        """
        通过 user_id 关联获取维修人员姓名
        """
        try:
            user = User.objects.get(id=obj.user_id)
            return user.nickname or user.username
        except User.DoesNotExist:
            return '未知用户'