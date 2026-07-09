from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class TemperatureRecord(models.Model):
    """
    温度历史记录表（映射 monitor_temperature_record 实时表）
    数据由 monitor 服务写入，本模块仅做查询与导出。
    """

    branch = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        verbose_name='支路编号',
    )
    timestamp = models.DateTimeField(
        verbose_name='记录时间点',
    )
    max_temp = models.FloatField(
        verbose_name='最高温度(℃)',
    )
    avg_temp = models.FloatField(
        verbose_name='平均温度(℃)',
    )
    area_ratio = models.FloatField(
        default=0.0,
        verbose_name='热斑面积占比(%)',
    )
    sample_count = models.IntegerField(
        default=1,
        verbose_name='采样次数',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间',
    )

    class Meta:
        managed = False
        db_table = 'monitor_temperature_record'
        verbose_name = '温度历史记录'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']

    def __str__(self):
        return f"支路{self.branch} - {self.timestamp} - {self.max_temp}℃"


class AlarmRecord(models.Model):
    """
    告警记录表（映射 monitor_alarm_record 实时表）
    数据由 monitor 服务写入，本模块仅做查询与导出。
    """

    ALARM_TYPE_CHOICES = [
        ('hot_spot', '热斑告警'),
        ('over_temp', '温度过载告警'),
        ('offline', '设备离线告警'),
    ]

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('recovering', '恢复中'),
        ('resolved', '已处理'),
    ]

    branch = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        verbose_name='支路编号',
    )
    alarm_type = models.CharField(
        max_length=32,
        choices=ALARM_TYPE_CHOICES,
        verbose_name='告警类型',
    )
    temperature = models.FloatField(
        null=True, blank=True,
        verbose_name='触发温度(℃)',
    )
    area_ratio = models.FloatField(
        null=True, blank=True,
        verbose_name='热斑面积占比(%)',
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处置状态',
    )
    image_path = models.CharField(
        max_length=512,
        blank=True, null=True,
        verbose_name='告警截图路径',
    )
    description = models.TextField(
        blank=True, null=True,
        verbose_name='告警描述',
    )
    auto_trip = models.BooleanField(
        default=False,
        verbose_name='是否自动分闸',
    )
    timestamp = models.DateTimeField(
        verbose_name='告警时间',
    )
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='处理时间',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间',
    )

    class Meta:
        managed = False
        db_table = 'monitor_alarm_record'
        verbose_name = '告警记录'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']

    def __str__(self):
        return f"支路{self.branch} - {self.get_alarm_type_display()} - {self.timestamp}"
