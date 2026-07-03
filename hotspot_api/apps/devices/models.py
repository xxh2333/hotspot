from django.db import models


class Device(models.Model):
    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '离线'),
        ('fault', '故障'),
        ('maintenance', '维护中'),
    ]
    
    DEVICE_TYPE_CHOICES = [
        ('meter', '电表'),
        ('switch', '开关'),
        ('sensor', '传感器'),
        ('controller', '控制器'),
    ]
    
    device_id = models.CharField(max_length=50, unique=True, verbose_name='设备ID')
    name = models.CharField(max_length=100, verbose_name='设备名称')
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPE_CHOICES, verbose_name='设备类型')
    branch = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='支路编号')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline', verbose_name='设备状态')
    location = models.CharField(max_length=200, null=True, blank=True, verbose_name='安装位置')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    last_active = models.DateTimeField(null=True, blank=True, verbose_name='最后活跃时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'devices'
        verbose_name = '设备'
        verbose_name_plural = '设备'
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['branch']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.device_id} - {self.name}"


class DeviceData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='data_records', verbose_name='关联设备')
    voltage = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='电压(V)')
    current = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='电流(A)')
    power = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='功率(W)')
    energy = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='电能(kWh)')
    temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='温度(℃)')
    humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='湿度(%)')
    power_factor = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, verbose_name='功率因数')
    frequency = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='频率(Hz)')
    data_time = models.DateTimeField(verbose_name='数据时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')
    
    class Meta:
        db_table = 'device_data'
        verbose_name = '设备数据'
        verbose_name_plural = '设备数据'
        indexes = [
            models.Index(fields=['device']),
            models.Index(fields=['-data_time']),
        ]
    
    def __str__(self):
        return f"{self.device.device_id} - {self.data_time}"


class DeviceControl(models.Model):
    CONTROL_TYPE_CHOICES = [
        ('switch_on', '合闸'),
        ('switch_off', '分闸'),
        ('reset', '复位'),
        ('calibrate', '校准'),
        ('configure', '配置'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('executed', '已执行'),
        ('failed', '执行失败'),
        ('timeout', '超时'),
    ]
    
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='control_records', verbose_name='关联设备')
    control_type = models.CharField(max_length=30, choices=CONTROL_TYPE_CHOICES, verbose_name='控制类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='执行状态')
    control_params = models.JSONField(null=True, blank=True, verbose_name='控制参数')
    response_data = models.JSONField(null=True, blank=True, verbose_name='响应数据')
    operator_id = models.BigIntegerField(null=True, blank=True, verbose_name='操作人ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    
    class Meta:
        db_table = 'device_controls'
        verbose_name = '设备控制记录'
        verbose_name_plural = '设备控制记录'
        indexes = [
            models.Index(fields=['device']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.device.device_id} - {self.get_control_type_display()}"