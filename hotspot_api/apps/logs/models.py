from django.db import models


class OperationLog(models.Model):
    """
    人员操作日志表
    """
    
    # 操作类型选项
    ACTION_TYPE_CHOICES = [
        ('remote_control', '远程分合闸控制'),
        ('threshold_update', '修改告警阈值'),
        ('repair_device', '维修设备'),
        ('reset_alarm', '告警复位'),
        ('system_estop', '系统紧急停止'),
    ]
    
    user_id = models.BigIntegerField(verbose_name='操作用户ID')
    branch = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='支路编号')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES, verbose_name='操作类型')
    is_success = models.BooleanField(default=True, verbose_name='操作是否成功')
    action_detail = models.JSONField(null=True, blank=True, verbose_name='操作详情')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(null=True, blank=True, verbose_name='浏览器标识')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')
    
    class Meta:
        db_table = 'operation_logs'
        verbose_name = '人员操作日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['user_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user_id} - {self.get_action_type_display()}"


class MaintenanceLog(models.Model):
    """
    故障排查处置日志表
    """
    
    alarm_id = models.BigIntegerField(verbose_name='关联告警ID')
    user_id = models.BigIntegerField(verbose_name='维修人员ID')
    fault_device = models.CharField(max_length=50, null=True, blank=True, verbose_name='故障设备类型')
    repair_detail = models.TextField(verbose_name='维修措施描述')
    repair_images = models.JSONField(null=True, blank=True, verbose_name='维修图片路径数组')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'maintenance_logs'
        verbose_name = '故障排查处置日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['alarm_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['alarm_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"告警{self.alarm_id} - 维修人员{self.user_id}"


class AlarmLog(models.Model):
    """
    告警日志表
    """
    
    class AlarmLevel(models.TextChoices):
        HOT_SPOT = 'hot_spot', '热斑告警'
        OVER_TEMP = 'over_temp', '温度过载告警'
        OFFLINE = 'offline', '设备离线告警'
    
    class ResolutionStatus(models.TextChoices):
        PENDING = 'pending', '未处理'
        RESOLVED = 'resolved', '已处理'
        RECOVERING = 'recovering', '恢复中'
    
    class ActionType(models.TextChoices):
        TRIP = 'trip', '跳闸'
        RESET = 'reset', '复位'
        NONE = 'none', '无动作'
    
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='告警触发时间')
    branch = models.PositiveSmallIntegerField(verbose_name='支路编号')
    alarm_level = models.CharField(max_length=20, choices=AlarmLevel.choices, verbose_name='告警分类')
    warning_level = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='严重等级(1/2/3)')
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name='告警描述')
    image_path = models.CharField(max_length=500, verbose_name='红外热成像原图路径')
    annotated_image_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='AI标注图路径')
    temperature = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='最高温度(℃)')
    temp_difference = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='局部温差(℃)')
    area_ratio = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='热斑面积占比(%)')
    threshold_temp = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='触发温度阈值(℃)')
    threshold_area = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='触发面积阈值(%)')
    auto_trip = models.BooleanField(default=True, verbose_name='是否自动跳闸')
    action = models.CharField(max_length=10, choices=ActionType.choices, null=True, blank=True, verbose_name='执行动作')
    resolution_status = models.CharField(max_length=20, choices=ResolutionStatus.choices, default='pending', verbose_name='处置状态')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='处置完成时间')
    resolved_by = models.BigIntegerField(null=True, blank=True, verbose_name='处置人ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='记录更新时间')
    
    class Meta:
        db_table = 'alarm_logs'
        verbose_name = '告警日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['branch']),
            models.Index(fields=['alarm_level']),
            models.Index(fields=['resolution_status']),
            models.Index(fields=['branch', 'timestamp']),
            models.Index(fields=['resolution_status', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.branch}号支路 - {self.get_alarm_level_display()}"