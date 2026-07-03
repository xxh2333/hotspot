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
        ]
    
    def __str__(self):
        return f"告警{self.alarm_id} - 维修人员{self.user_id}"