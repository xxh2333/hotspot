from django.db import models


class TemperatureRecord(models.Model):
    """
    温度历史记录表
    存储各支路温度采集的原始历史数据，用于历史温度查询、表格展示和 Excel 导出。
    数据来源：树莓派通过 MQTT 每 5 秒上报一次温度数据。
    """

    branch = models.PositiveSmallIntegerField(
        verbose_name='支路编号',
        db_index=True,
        help_text='取值 1~4',
    )
    timestamp = models.DateTimeField(
        verbose_name='采集时间（毫秒精度）',
        db_index=True,
        help_text='树莓派数据采集的时间戳，精确到毫秒',
    )
    max_temp = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name='最高温度（℃）',
        help_text='该支路在当前采集周期内的最高温度',
    )
    min_temp = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='最低温度（℃）',
        help_text='该支路在当前采集周期内的最低温度',
    )
    avg_temp = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='平均温度（℃）',
        help_text='该支路在当前采集周期内的平均温度',
    )
    area_ratio = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.00,
        verbose_name='热斑面积占比（%）',
        help_text='热斑区域面积占光伏板总面积的百分比',
    )
    hotspot_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='热斑数量',
        help_text='当前采集周期内检测到的热斑个数',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='记录创建时间',
        help_text='数据入库时间',
    )

    class Meta:
        db_table = 'temperature_records'
        verbose_name = '温度历史记录'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['branch', 'timestamp'], name='idx_temp_rec_branch_ts'),
            models.Index(fields=['timestamp'], name='idx_temp_rec_ts'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4),
                name='chk_temp_rec_branch',
            ),
            models.CheckConstraint(
                check=models.Q(max_temp__gte=-20, max_temp__lte=150),
                name='chk_temp_rec_max_temp',
            ),
            models.CheckConstraint(
                check=models.Q(area_ratio__gte=0, area_ratio__lte=100),
                name='chk_temp_rec_area_ratio',
            ),
        ]

    def __str__(self):
        return f"支路{self.branch} - {self.timestamp} - {self.max_temp}℃"


class AlarmRecord(models.Model):
    """
    告警记录表
    存储系统自动触发的所有告警事件历史数据，用于历史告警查询、表格展示和 Excel 导出。
    告警由后端判决逻辑自动生成，本表仅记录，不参与告警触发逻辑。
    """

    # ── 告警类型枚举（整数） ──
    ALARM_TYPES = [
        (1, "热斑告警"),
        (2, "温度过载告警"),
        (3, "设备离线告警"),
    ]

    class WarningLevel(models.IntegerChoices):
        LEVEL_1 = 1, '一级告警'
        LEVEL_2 = 2, '二级告警'
        LEVEL_3 = 3, '三级告警'

    class ResolutionStatus(models.TextChoices):
        PENDING = 'pending', '未处理'
        RESOLVED = 'resolved', '已处理'
        RECOVERING = 'recovering', '恢复中'

    class ActionType(models.TextChoices):
        TRIP = 'trip', '跳闸'
        RESET = 'reset', '复位'
        NONE = 'none', '无动作'

    # ── 核心字段 ──
    branch = models.PositiveSmallIntegerField(
        verbose_name='支路编号',
        db_index=True,
        help_text='取值 1~4',
    )
    trigger_time = models.DateTimeField(
        verbose_name='告警触发时间（毫秒精度）',
        db_index=True,
        help_text='告警触发的时间戳，精确到毫秒',
    )
    alarm_type = models.PositiveSmallIntegerField(
        choices=ALARM_TYPES,
        verbose_name='告警类型',
        db_index=True,
        help_text='1=热斑告警, 2=温度过载告警, 3=设备离线告警',
    )
    warning_level = models.PositiveSmallIntegerField(
        choices=WarningLevel.choices,
        null=True, blank=True,
        verbose_name='严重等级',
        help_text='1=一级（最严重）, 2=二级, 3=三级',
    )

    # ── 描述与图片 ──
    description = models.CharField(
        max_length=255,
        null=True, blank=True,
        verbose_name='告警描述',
    )
    image_path = models.CharField(
        max_length=500,
        verbose_name='红外热成像原图路径',
    )
    annotated_image_path = models.CharField(
        max_length=500,
        null=True, blank=True,
        verbose_name='带AI标注的图片路径',
    )

    # ── 温度与面积数据 ──
    temperature = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name='最高温度（℃）',
        help_text='触发告警时的热斑区域最高温度',
    )
    temp_difference = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='局部温差（℃）',
    )
    area_ratio = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name='热斑面积占比（%）',
    )

    # ── 触发阈值快照 ──
    threshold_temp = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name='温度阈值（℃）',
        help_text='告警触发时的温度阈值快照',
    )
    threshold_area = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name='面积阈值（%）',
        help_text='告警触发时的面积阈值快照',
    )

    # ── 执行动作 ──
    auto_trip = models.BooleanField(
        default=True,
        verbose_name='是否自动跳闸',
    )
    action = models.CharField(
        max_length=10,
        choices=ActionType.choices,
        null=True, blank=True,
        verbose_name='执行动作',
    )

    # ── 处置状态 ──
    resolution_status = models.CharField(
        max_length=20,
        choices=ResolutionStatus.choices,
        default='pending',
        db_index=True,
        verbose_name='处置状态',
    )
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='处置完成时间',
    )
    resolved_by = models.CharField(
        max_length=150,
        null=True, blank=True,
        verbose_name='处置人用户名',
    )

    # ── 审计时间 ──
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='记录创建时间',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='记录更新时间',
    )

    class Meta:
        db_table = 'alarm_records'
        verbose_name = '告警记录'
        verbose_name_plural = verbose_name
        ordering = ['-trigger_time']
        indexes = [
            models.Index(fields=['branch', 'trigger_time'], name='idx_alarm_rec_branch_tt'),
            models.Index(fields=['alarm_type'], name='idx_alarm_rec_type'),
            models.Index(fields=['resolution_status'], name='idx_alarm_rec_status'),
            models.Index(fields=['resolution_status', 'trigger_time'], name='idx_alarm_rec_status_tt'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4),
                name='chk_alarm_rec_branch',
            ),
            models.CheckConstraint(
                check=models.Q(alarm_type__in=[1, 2, 3]),
                name='chk_alarm_rec_type',
            ),
            models.CheckConstraint(
                check=models.Q(temperature__gte=-20, temperature__lte=150),
                name='chk_alarm_rec_temperature',
            ),
            models.CheckConstraint(
                check=models.Q(area_ratio__gte=0, area_ratio__lte=100),
                name='chk_alarm_rec_area_ratio',
            ),
            models.CheckConstraint(
                check=models.Q(warning_level__in=[1, 2, 3]) | models.Q(warning_level__isnull=True),
                name='chk_alarm_rec_warning_level',
            ),
        ]

    def __str__(self):
        return f"支路{self.branch} - {self.get_alarm_type_display()} - {self.trigger_time}"
