from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TemperatureDailyStats',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stat_date', models.DateField(verbose_name='统计日期')),
                ('branch', models.PositiveSmallIntegerField(verbose_name='支路编号')),
                ('avg_max_temp', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='当日平均最高温度（℃）')),
                ('peak_temp', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='当日峰值温度（℃）')),
                ('avg_area_ratio', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='当日平均热斑面积占比（%）')),
                ('max_area_ratio', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='当日最大热斑面积占比（%）')),
                ('sample_count', models.PositiveIntegerField(default=0, verbose_name='当日原始采样条数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')),
            ],
            options={
                'verbose_name': '温度日聚合统计',
                'verbose_name_plural': '温度日聚合统计',
                'db_table': 'temperature_daily_stats',
            },
        ),
        migrations.CreateModel(
            name='TemperatureLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(verbose_name='采集时间戳（毫秒精度）')),
                ('branch', models.PositiveSmallIntegerField(verbose_name='支路编号')),
                ('max_temp', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='该支路最高温度（℃）')),
                ('min_temp', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='该支路最低温度（℃）')),
                ('avg_temp', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='该支路平均温度（℃）')),
                ('area_ratio', models.DecimalField(decimal_places=2, default=0.0, max_digits=5, verbose_name='热斑面积占比（%）')),
                ('hotspot_count', models.PositiveSmallIntegerField(default=0, verbose_name='热斑数量')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间（入库时间）')),
            ],
            options={
                'verbose_name': '温度日志',
                'verbose_name_plural': '温度日志',
                'db_table': 'temperature_logs',
            },
        ),
        migrations.AddIndex(
            model_name='temperaturelog',
            index=models.Index(fields=['timestamp'], name='idx_temp_timestamp'),
        ),
        migrations.AddIndex(
            model_name='temperaturelog',
            index=models.Index(fields=['branch'], name='idx_temp_branch'),
        ),
        migrations.AddIndex(
            model_name='temperaturelog',
            index=models.Index(fields=['branch', 'timestamp'], name='idx_temp_branch_timestamp'),
        ),
        migrations.AddConstraint(
            model_name='temperaturelog',
            constraint=models.UniqueConstraint(fields=['branch', 'timestamp'], name='uk_temperature_logs_branch_timestamp'),
        ),
        migrations.AddConstraint(
            model_name='temperaturelog',
            constraint=models.CheckConstraint(check=models.Q(('branch__gte', 1), ('branch__lte', 4)), name='chk_temperature_logs_branch'),
        ),
        migrations.AddConstraint(
            model_name='temperaturelog',
            constraint=models.CheckConstraint(check=models.Q(('max_temp__gte', -20), ('max_temp__lte', 150)), name='chk_temperature_logs_max_temp'),
        ),
        migrations.AddConstraint(
            model_name='temperaturelog',
            constraint=models.CheckConstraint(check=models.Q(('area_ratio__gte', 0), ('area_ratio__lte', 100)), name='chk_temperature_logs_area_ratio'),
        ),
        migrations.AddIndex(
            model_name='temperaturedailystats',
            index=models.Index(fields=['stat_date'], name='idx_daily_stats_date'),
        ),
        migrations.AddIndex(
            model_name='temperaturedailystats',
            index=models.Index(fields=['branch', 'stat_date'], name='idx_daily_stats_branch_date'),
        ),
        migrations.AddConstraint(
            model_name='temperaturedailystats',
            constraint=models.UniqueConstraint(fields=['stat_date', 'branch'], name='uk_daily_stats_date_branch'),
        ),
        migrations.AddConstraint(
            model_name='temperaturedailystats',
            constraint=models.CheckConstraint(check=models.Q(('branch__gte', 1), ('branch__lte', 4)), name='chk_daily_stats_branch'),
        ),
    ]