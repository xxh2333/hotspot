from rest_framework import serializers

from django.contrib.auth import get_user_model

from .models import OperationLog, MaintenanceLog, AlarmLog

User = get_user_model()

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S'


class OperationLogSerializer(serializers.ModelSerializer):
    """
    人员操作日志序列化器
    """
    operator_name = serializers.SerializerMethodField(read_only=True)
    maintenance_status_display = serializers.SerializerMethodField(read_only=True)
    created_at = serializers.DateTimeField(format=DATETIME_FORMAT, read_only=True)

    class Meta:
        model = OperationLog
        fields = ['id', 'operator_name', 'branch', 'action_type', 'maintenance_status',
                  'maintenance_status_display', 'action_detail', 'created_at']

    def get_operator_name(self, obj):
        """
        通过 user_id 关联获取用户名
        """
        try:
            user = User.objects.get(id=obj.user_id)
            return user.username
        except User.DoesNotExist:
            return '未知用户'

    def get_maintenance_status_display(self, obj):
        """
        获取维护状态的中文显示
        """
        return obj.get_maintenance_status_display()


class MaintenanceLogSerializer(serializers.ModelSerializer):
    """
    故障处置日志序列化器
    """
    fault_date = serializers.SerializerMethodField(read_only=True)
    fault_time = serializers.SerializerMethodField(read_only=True)
    device_code = serializers.SerializerMethodField(read_only=True)
    images = serializers.JSONField(source='repair_images', read_only=True)
    repairer_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MaintenanceLog
        fields = ['id', 'fault_date', 'fault_time', 'fault_device', 'device_code',
                  'images', 'repairer_name', 'repair_detail', 'remark']

    def get_fault_date(self, obj):
        """
        获取 created_at 的日期部分，格式 YYYY-MM-DD
        """
        return obj.created_at.strftime(DATE_FORMAT) if obj.created_at else None

    def get_fault_time(self, obj):
        """
        获取 created_at 的时间部分，格式 HH:MM:SS
        """
        return obj.created_at.strftime(TIME_FORMAT) if obj.created_at else None

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
            return user.username
        except User.DoesNotExist:
            return '未知用户'


class CreateOperationLogSerializer(serializers.Serializer):
    """
    新增人员操作日志序列化器
    """
    MAINTENANCE_STATUS_CHOICES = [
        ('maintained', '已维护'),
        ('maintaining', '维护中'),
        ('unmaintained', '未维护'),
    ]

    branch = serializers.IntegerField(min_value=1, max_value=4, help_text='支路编号（1-4）')
    action_type = serializers.ChoiceField(choices=OperationLog.ACTION_TYPE_CHOICES, help_text='操作类型')
    maintenance_status = serializers.ChoiceField(choices=MAINTENANCE_STATUS_CHOICES, help_text='维护状态')
    action_detail = serializers.JSONField(required=False, default=dict, help_text='操作详情')

    def validate_branch(self, value):
        """验证支路编号范围为 1-4"""
        if value < 1 or value > 4:
            raise serializers.ValidationError('支路编号必须在 1-4 之间')
        return value


class CreateMaintenanceLogSerializer(serializers.Serializer):
    """
    新增故障处置日志序列化器
    """
    alarm_id = serializers.IntegerField(min_value=1, help_text='关联告警ID')
    fault_device = serializers.CharField(max_length=50, required=False, allow_blank=True, default='', help_text='故障设备类型')
    repair_detail = serializers.CharField(help_text='维修措施描述')
    repair_images = serializers.JSONField(required=False, default=list, help_text='图片URL数组')
    remark = serializers.CharField(required=False, allow_blank=True, default='', help_text='备注信息')