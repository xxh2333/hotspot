# Generated manually — 设备历史记录模块初始迁移

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        # ────────────────────────────────────────────
        # 1. 温度历史记录表
        # ────────────────────────────────────────────
        migrations.CreateModel(
            name='TemperatureRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('branch', models.PositiveSmallIntegerField(db_index=True, help_text='取值 1~4', verbose_name='支路编号')),
                ('timestamp', models.DateTimeField(db_index=True, help_text='树莓派数据采集的时间戳，精确到毫秒', verbose_name='采集时间（毫秒精度）')),
                ('max_temp', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='最高温度（℃）')),
                ('min_temp', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='最低温度（℃）')),
                ('avg_temp', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='平均温度（℃）')),
                ('area_ratio', models.DecimalField(decimal_places=2, default=0.0, max_digits=5, verbose_name='热斑面积占比（%）')),
                ('hotspot_count', models.PositiveSmallIntegerField(default=0, verbose_name='热斑数量')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')),
            ],
            options={
                'verbose_name': '温度历史记录',
                'verbose_name_plural': '温度历史记录',
                'db_table': 'temperature_records',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['branch', 'timestamp'], name='idx_temp_rec_branch_ts'),
                    models.Index(fields=['timestamp'], name='idx_temp_rec_ts'),
                ],
            },
        ),

        # ────────────────────────────────────────────
        # 2. 告警记录表
        # ────────────────────────────────────────────
        migrations.CreateModel(
            name='AlarmRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('branch', models.PositiveSmallIntegerField(db_index=True, help_text='取值 1~4', verbose_name='支路编号')),
                ('trigger_time', models.DateTimeField(db_index=True, help_text='告警触发的时间戳，精确到毫秒', verbose_name='告警触发时间（毫秒精度）')),
                ('alarm_type', models.PositiveSmallIntegerField(choices=[(1, '热斑告警'), (2, '温度过载告警'), (3, '设备离线告警')], db_index=True, help_text='1=热斑告警, 2=温度过载告警, 3=设备离线告警', verbose_name='告警类型')),
                ('warning_level', models.PositiveSmallIntegerField(blank=True, choices=[(1, '一级告警'), (2, '二级告警'), (3, '三级告警')], null=True, verbose_name='严重等级')),
                ('description', models.CharField(blank=True, max_length=255, null=True, verbose_name='告警描述')),
                ('image_path', models.CharField(max_length=500, verbose_name='红外热成像原图路径')),
                ('annotated_image_path', models.CharField(blank=True, max_length=500, null=True, verbose_name='带AI标注的图片路径')),
                ('temperature', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='最高温度（℃）')),
                ('temp_difference', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='局部温差（℃）')),
                ('area_ratio', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='热斑面积占比（%）')),
                ('threshold_temp', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='温度阈值（℃）')),
                ('threshold_area', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='面积阈值（%）')),
                ('auto_trip', models.BooleanField(default=True, verbose_name='是否自动跳闸')),
                ('action', models.CharField(blank=True, choices=[('trip', '跳闸'), ('reset', '复位'), ('none', '无动作')], max_length=10, null=True, verbose_name='执行动作')),
                ('resolution_status', models.CharField(choices=[('pending', '未处理'), ('resolved', '已处理'), ('recovering', '恢复中')], db_index=True, default='pending', max_length=20, verbose_name='处置状态')),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='处置完成时间')),
                ('resolved_by', models.CharField(blank=True, max_length=150, null=True, verbose_name='处置人用户名')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='记录创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='记录更新时间')),
            ],
            options={
                'verbose_name': '告警记录',
                'verbose_name_plural': '告警记录',
                'db_table': 'alarm_records',
                'ordering': ['-trigger_time'],
                'indexes': [
                    models.Index(fields=['branch', 'trigger_time'], name='idx_alarm_rec_branch_tt'),
                    models.Index(fields=['alarm_type'], name='idx_alarm_rec_type'),
                    models.Index(fields=['resolution_status'], name='idx_alarm_rec_status'),
                    models.Index(fields=['resolution_status', 'trigger_time'], name='idx_alarm_rec_status_tt'),
                ],
            },
        ),

        # ────────────────────────────────────────────
        # 3. 添加 CheckConstraint 约束
        # ────────────────────────────────────────────
        migrations.AddConstraint(
            model_name='temperaturerecord',
            constraint=models.CheckConstraint(
                check=models.Q(('branch__gte', 1), ('branch__lte', 4)),
                name='chk_temp_rec_branch',
            ),
        ),
        migrations.AddConstraint(
            model_name='temperaturerecord',
            constraint=models.CheckConstraint(
                check=models.Q(('max_temp__gte', -20), ('max_temp__lte', 150)),
                name='chk_temp_rec_max_temp',
            ),
        ),
        migrations.AddConstraint(
            model_name='temperaturerecord',
            constraint=models.CheckConstraint(
                check=models.Q(('area_ratio__gte', 0), ('area_ratio__lte', 100)),
                name='chk_temp_rec_area_ratio',
            ),
        ),

        migrations.AddConstraint(
            model_name='alarmrecord',
            constraint=models.CheckConstraint(
                check=models.Q(('branch__gte', 1), ('branch__lte', 4)),
                name='chk_alarm_rec_branch',
            ),
        ),
        migrations.AddConstraint(
            model_name='alarmrecord',
            constraint=models.CheckConstraint(
                check=models.Q(('alarm_type__in', [1, 2, 3])),
                name='chk_alarm_rec_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='alarmrecord',
            constraint=models.CheckConstraint(
                check=models.Q(('temperature__gte', -20), ('temperature__lte', 150)),
                name='chk_alarm_rec_temperature',
            ),
        ),
        migrations.AddConstraint(
            model_name='alarmrecord',
            constraint=models.CheckConstraint(
                check=models.Q(('area_ratio__gte', 0), ('area_ratio__lte', 100)),
                name='chk_alarm_rec_area_ratio',
            ),
        ),
        migrations.AddConstraint(
            model_name='alarmrecord',
            constraint=models.CheckConstraint(
                check=models.Q(('warning_level__in', [1, 2, 3]), ('warning_level__isnull', True), _connector=models.Q.OR),
                name='chk_alarm_rec_warning_level',
            ),
        ),

        # ────────────────────────────────────────────
        # 4. 显式指定 InnoDB 引擎
        # ────────────────────────────────────────────
        migrations.RunSQL(
            "ALTER TABLE temperature_records ENGINE=InnoDB;",
            reverse_sql="ALTER TABLE temperature_records ENGINE=InnoDB;",
        ),
        migrations.RunSQL(
            "ALTER TABLE alarm_records ENGINE=InnoDB;",
            reverse_sql="ALTER TABLE alarm_records ENGINE=InnoDB;",
        ),
    ]
