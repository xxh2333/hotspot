from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class BranchStatus(models.Model):
    """
    支路实时状态表
    存储各支路最新一次采集的温度和状态快照
    """
    BRANCH_CHOICES = [(i, f'支路{i}') for i in range(1, 5)]

    BREAKER_STATUS_CHOICES = [
        ('closed', '合闸'),
        ('open', '分闸'),
    ]

    ALARM_STATUS_CHOICES = [
        ('normal', '正常'),
        ('alarm', '告警'),
    ]

    branch = models.IntegerField(choices=BRANCH_CHOICES, unique=True, verbose_name='支路编号')
    temperature = models.FloatField(default=0.0, verbose_name='当前最高温度(℃)')
    area_ratio = models.FloatField(default=0.0, verbose_name='热斑面积占比(%)')
    breaker_status = models.CharField(
        max_length=16, choices=BREAKER_STATUS_CHOICES, default='closed', verbose_name='断路器状态'
    )
    alarm_status = models.CharField(
        max_length=16, choices=ALARM_STATUS_CHOICES, default='normal', verbose_name='告警状态'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')

    class Meta:
        db_table = 'monitor_branch_status'
        verbose_name = '支路实时状态'
        verbose_name_plural = '支路实时状态'

    def __str__(self):
        return f'支路{self.branch} - {self.temperature}℃'


class TemperatureRecord(models.Model):
    """
    温度历史记录表
    存储各支路按小时/天聚合的温度数据
    """
    branch = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)], verbose_name='支路编号')
    timestamp = models.DateTimeField(verbose_name='记录时间点')
    max_temp = models.FloatField(verbose_name='最高温度(℃)')
    avg_temp = models.FloatField(verbose_name='平均温度(℃)')
    area_ratio = models.FloatField(default=0.0, verbose_name='热斑面积占比(%)')
    sample_count = models.IntegerField(default=1, verbose_name='采样次数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'monitor_temperature_record'
        verbose_name = '温度历史记录'
        verbose_name_plural = '温度历史记录'
        indexes = [
            models.Index(fields=['branch', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'支路{self.branch} {self.timestamp} max={self.max_temp}℃'


class AlarmRecord(models.Model):
    """
    告警记录表
    存储所有告警事件，支持分页和筛选
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

    branch = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)], verbose_name='支路编号')
    alarm_type = models.CharField(max_length=32, choices=ALARM_TYPE_CHOICES, verbose_name='告警类型')
    temperature = models.FloatField(null=True, blank=True, verbose_name='触发温度(℃)')
    area_ratio = models.FloatField(null=True, blank=True, verbose_name='热斑面积占比(%)')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending', verbose_name='处置状态')
    image_path = models.CharField(max_length=512, blank=True, null=True, verbose_name='告警截图路径')
    description = models.TextField(blank=True, null=True, verbose_name='告警描述')
    auto_trip = models.BooleanField(default=False, verbose_name='是否自动分闸')
    timestamp = models.DateTimeField(verbose_name='告警时间')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'monitor_alarm_record'
        verbose_name = '告警记录'
        verbose_name_plural = '告警记录'
        indexes = [
            models.Index(fields=['branch', 'timestamp']),
            models.Index(fields=['alarm_type']),
            models.Index(fields=['status']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.get_alarm_type_display()}] 支路{self.branch} {self.timestamp}'


class SystemConfig(models.Model):
    """
    系统配置表
    存储告警阈值等运行时可调参数
    """
    CONFIG_KEY_CHOICES = [
        ('temperature_threshold', '温度告警阈值(℃)'),
        ('area_ratio_threshold', '面积告警阈值(%)'),
        ('mqtt_broker_host', 'MQTT Broker地址'),
        ('mqtt_broker_port', 'MQTT Broker端口'),
        ('data_retention_days', '数据保留天数'),
    ]

    config_key = models.CharField(max_length=64, choices=CONFIG_KEY_CHOICES, unique=True, verbose_name='配置键')
    config_value = models.CharField(max_length=256, verbose_name='配置值')
    description = models.CharField(max_length=256, blank=True, null=True, verbose_name='配置说明')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'monitor_system_config'
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'

    def __str__(self):
        return f'{self.get_config_key_display()}: {self.config_value}'


class DeviceStatus(models.Model):
    """
    设备状态表
    记录热像仪和MQTT等设备的在线状态
    """
    DEVICE_TYPE_CHOICES = [
        ('thermal_camera', '热像仪'),
        ('mqtt', 'MQTT服务'),
        ('raspberrypi', '树莓派'),
    ]

    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '离线'),
    ]

    device_type = models.CharField(max_length=32, choices=DEVICE_TYPE_CHOICES, verbose_name='设备类型')
    device_id = models.CharField(max_length=128, default='default', verbose_name='设备标识')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='offline', verbose_name='在线状态')
    extra_info = models.JSONField(default=dict, blank=True, verbose_name='附加信息')
    last_seen = models.DateTimeField(auto_now=True, verbose_name='最后在线时间')

    class Meta:
        db_table = 'monitor_device_status'
        verbose_name = '设备状态'
        verbose_name_plural = '设备状态'
        unique_together = ['device_type', 'device_id']

    def __str__(self):
        return f'{self.get_device_type_display()} [{self.device_id}]: {self.status}'


class ThermalImage(models.Model):
    """
    红外热像图表
    存储红外图像帧的元数据和文件路径
    """
    timestamp = models.DateTimeField(verbose_name='采集时间')
    device_id = models.CharField(max_length=128, default='raspberrypi-01', verbose_name='设备标识')
    image_path = models.CharField(max_length=512, verbose_name='原始图像路径')
    annotated_path = models.CharField(max_length=512, blank=True, null=True, verbose_name='标注图像路径')
    width = models.IntegerField(default=256, verbose_name='图像宽度')
    height = models.IntegerField(default=192, verbose_name='图像高度')
    hotspots = models.JSONField(default=list, blank=True, verbose_name='热斑坐标信息')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'monitor_thermal_image'
        verbose_name = '红外热像图'
        verbose_name_plural = '红外热像图'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['device_id', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'热像图 {self.timestamp} [{self.width}x{self.height}]'
