from django.db import models


class TemperatureLog(models.Model):
    """
    温度日志表
    存储树莓派每 5 秒上报的原始温度与热斑数据，保留 7 天
    数据来源：树莓派后端主程序每 5 秒写入一条
    """

    timestamp = models.DateTimeField(verbose_name='采集时间戳（毫秒精度）')
    branch = models.PositiveSmallIntegerField(verbose_name='支路编号')
    max_temp = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='该支路最高温度（℃）')
    min_temp = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='该支路最低温度（℃）')
    avg_temp = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='该支路平均温度（℃）')
    area_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='热斑面积占比（%）')
    hotspot_count = models.PositiveSmallIntegerField(default=0, verbose_name='热斑数量')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间（入库时间）')

    class Meta:
        db_table = 'temperature_logs'
        verbose_name = '温度日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['timestamp'], name='idx_temp_timestamp'),
            models.Index(fields=['branch'], name='idx_temp_branch'),
            models.Index(fields=['branch', 'timestamp'], name='idx_temp_branch_timestamp'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['branch', 'timestamp'],
                name='uk_temperature_logs_branch_timestamp',
            ),
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4),
                name='chk_temperature_logs_branch',
            ),
            models.CheckConstraint(
                check=models.Q(max_temp__gte=-20, max_temp__lte=150),
                name='chk_temperature_logs_max_temp',
            ),
            models.CheckConstraint(
                check=models.Q(area_ratio__gte=0, area_ratio__lte=100),
                name='chk_temperature_logs_area_ratio',
            ),
        ]

    def __str__(self):
        return f"支路{branch} - {self.timestamp} - {self.max_temp}℃"


class TemperatureDailyStats(models.Model):
    """
    温度日聚合统计表
    由定时任务每天凌晨从 temperature_logs 聚合前一天数据写入，保留 30 天
    专门支撑趋势图表模块的 30 天历史查询
    """

    stat_date = models.DateField(verbose_name='统计日期')
    branch = models.PositiveSmallIntegerField(verbose_name='支路编号')
    avg_max_temp = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='当日平均最高温度（℃）')
    peak_temp = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='当日峰值温度（℃）')
    avg_area_ratio = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='当日平均热斑面积占比（%）')
    max_area_ratio = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='当日最大热斑面积占比（%）')
    sample_count = models.PositiveIntegerField(default=0, verbose_name='当日原始采样条数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')

    class Meta:
        db_table = 'temperature_daily_stats'
        verbose_name = '温度日聚合统计'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['stat_date'], name='idx_daily_stats_date'),
            models.Index(fields=['branch', 'stat_date'], name='idx_daily_stats_branch_date'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['stat_date', 'branch'],
                name='uk_daily_stats_date_branch',
            ),
            models.CheckConstraint(
                check=models.Q(branch__gte=1, branch__lte=4),
                name='chk_daily_stats_branch',
            ),
        ]

    def __str__(self):
        return f"支路{branch} - {self.stat_date} - 峰值{self.peak_temp}℃"
