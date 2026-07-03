from django.db import models


class AlarmLog(models.Model):
    """
    告警日志表
    记录系统自动触发的所有告警事件，由告警判决模块负责写入，其他模块仅读取
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

    timestamp = models.DateTimeField(verbose_name='告警触发时间')
    branch = models.PositiveSmallIntegerField(verbose_name='支路编号')
    alarm_level = models.CharField(max_length=20, choices=AlarmLevel.choices, verbose_name='告警分类')
    warning_level = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='严重等级（1/2/3）')
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name='告警描述')
    image_path = models.CharField(max_length=500, verbose_name='红外热成像原图路径')
    annotated_image_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='带AI标注的告警图片路径')
    temperature = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='触发告警时的最高温度（℃）')
    temp_difference = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='局部温差（℃）')
    area_ratio = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='热斑面积占比（%）')
    threshold_temp = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='触发时的温度阈值（℃）')
    threshold_area = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='触发时的面积阈值（%）')
    auto_trip = models.BooleanField(default=True, verbose_name='是否自动跳闸')
    action = models.CharField(max_length=10, choices=ActionType.choices, null=True, blank=True, verbose_name='执行动作')
    resolution_status = models.CharField(
        max_length=20, choices=ResolutionStatus.choices, default='pending', verbose_name='处置状态'
    )
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='处置完成/恢复时间')
    resolved_by = models.BigIntegerField(null=True, blank=True, verbose_name='处置人ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='记录更新时间')

    class Meta:
        db_table = 'alarm_logs'
        verbose_name = '告警日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['timestamp'], name='idx_alarm_timestamp'),
            models.Index(fields=['branch'], name='idx_alarm_branch'),
            models.Index(fields=['alarm_level'], name='idx_alarm_level'),
            models.Index(fields=['resolution_status'], name='idx_alarm_resolution_status'),
            models.Index(fields=['branch', 'timestamp'], name='idx_alarm_branch_timestamp'),
            models.Index(fields=['resolution_status', 'timestamp'], name='idx_alarm_status_timestamp'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4),
                name='chk_alarm_logs_branch',
            ),
            models.CheckConstraint(
                check=models.Q(temperature__gte=-20, temperature__lte=150),
                name='chk_alarm_logs_temperature',
            ),
            models.CheckConstraint(
                check=models.Q(area_ratio__gte=0, area_ratio__lte=100),
                name='chk_alarm_logs_area_ratio',
            ),
            models.CheckConstraint(
                check=models.Q(warning_level__in=[1, 2, 3]) | models.Q(warning_level__isnull=True),
                name='chk_alarm_logs_warning_level',
            ),
        ]

    def __str__(self):
        return f"{self.branch}号支路 - {self.get_alarm_level_display()}"


class OperationLog(models.Model):
    """
    人员操作日志表
    记录用户在系统中的所有操作行为，用于操作审计和问题追溯
    """

    ACTION_TYPE_CHOICES = [
        ('remote_control', '远程分合闸控制'),
        ('threshold_update', '修改告警阈值'),
        ('repair_device', '维修设备'),
        ('reset_alarm', '告警复位'),
        ('system_estop', '系统紧急停止'),
    ]

    user_id = models.BigIntegerField(verbose_name='操作用户ID')
    branch = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='操作的支路编号')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES, verbose_name='操作类型')
    is_success = models.BooleanField(default=True, verbose_name='操作是否成功')
    action_detail = models.JSONField(null=True, blank=True, verbose_name='操作详情（JSON格式）')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='操作来源IP地址')
    user_agent = models.TextField(null=True, blank=True, verbose_name='浏览器/客户端标识')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        db_table = 'operation_logs'
        verbose_name = '人员操作日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['user_id'], name='idx_op_user_id'),
            models.Index(fields=['branch'], name='idx_op_branch'),
            models.Index(fields=['-created_at'], name='idx_op_created_at'),
            models.Index(fields=['user_id', 'created_at'], name='idx_op_user_created'),
            models.Index(fields=['action_type'], name='idx_op_action_type'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4) | models.Q(branch__isnull=True),
                name='chk_operation_logs_branch',
            ),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.get_action_type_display()}"


class MaintenanceLog(models.Model):
    """
    故障排查处置日志表（V3.1）
    记录运维人员对故障进行排查和维修处置的全过程
    """

    alarm_id = models.BigIntegerField(null=True, blank=True, verbose_name='关联的告警记录ID')
    user_id = models.BigIntegerField(verbose_name='维修人员ID')
    fault_date = models.DateField(verbose_name='故障日期')
    fault_time = models.TimeField(verbose_name='故障时间')
    branch = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='故障支路编号')
    fault_device = models.CharField(max_length=50, null=True, blank=True, verbose_name='故障设备类型')
    repair_detail = models.TextField(verbose_name='维修措施详细描述')
    repair_images = models.JSONField(null=True, blank=True, verbose_name='维修现场图片路径数组')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='处置记录创建时间')

    class Meta:
        db_table = 'maintenance_logs'
        verbose_name = '故障排查处置日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['alarm_id'], name='idx_mt_alarm_id'),
            models.Index(fields=['user_id'], name='idx_mt_user_id'),
            models.Index(fields=['-created_at'], name='idx_mt_created_at'),
            models.Index(fields=['alarm_id', 'created_at'], name='idx_mt_alarm_created'),
            models.Index(fields=['branch'], name='idx_mt_branch'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4) | models.Q(branch__isnull=True),
                name='chk_maintenance_logs_branch',
            ),
        ]

    def __str__(self):
        return f"告警{self.alarm_id or 'N/A'} - 维修人员{self.user_id}"


class SystemConfig(models.Model):
    """
    系统配置表（V3.1 新增）
    存储系统运行时配置参数（如告警阈值），避免将配置值硬编码或从历史告警快照中读取
    """

    config_key = models.CharField(max_length=50, unique=True, verbose_name='配置键名')
    config_value = models.CharField(max_length=255, verbose_name='配置值')
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name='配置说明')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')
    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name='最后更新人ID')

    class Meta:
        db_table = 'system_config'
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.config_key} = {self.config_value}"
