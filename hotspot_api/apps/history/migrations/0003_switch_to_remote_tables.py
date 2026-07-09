"""
将 history 模块的 TemperatureRecord / AlarmRecord 切换到远程实时表。
所有操作均使用 state_only=True，不执行实际 DDL，因为远程表已存在。
旧表（temperature_records / alarm_records）由用户自行决定是否清理。

使用方式（首次连接远程库时）：
    1. python manage.py migrate history --fake-initial
    2. python manage.py migrate history
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('history', '0002_alter_alarmrecord_temperature_and_more'),
    ]

    def _state_only(table_name, operation):
        """将 operation 包装为仅状态变更，不执行实际 DDL"""
        return migrations.SeparateDatabaseAndState(
            state_operations=[operation],
            database_operations=[],
        )

    operations = [
        # ════════════════════════════════════════
        # TemperatureRecord
        # ════════════════════════════════════════
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelTable(
                    name='temperaturerecord',
                    table='monitor_temperature_record',
                ),
                migrations.AlterModelOptions(
                    name='temperaturerecord',
                    options={
                        'managed': False,
                        'verbose_name': '温度历史记录',
                        'verbose_name_plural': '温度历史记录',
                        'ordering': ['-timestamp'],
                    },
                ),
                # 清理旧的状态索引/约束，这些在远程表上不存在
                migrations.RemoveIndex(
                    model_name='temperaturerecord',
                    name='idx_temp_rec_branch_ts',
                ),
                migrations.RemoveIndex(
                    model_name='temperaturerecord',
                    name='idx_temp_rec_ts',
                ),
                migrations.RemoveConstraint(
                    model_name='temperaturerecord',
                    name='chk_temp_rec_branch',
                ),
                migrations.RemoveConstraint(
                    model_name='temperaturerecord',
                    name='chk_temp_rec_max_temp',
                ),
                migrations.RemoveConstraint(
                    model_name='temperaturerecord',
                    name='chk_temp_rec_area_ratio',
                ),
            ],
            database_operations=[],
        ),

        # ════════════════════════════════════════
        # AlarmRecord
        # ════════════════════════════════════════
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelTable(
                    name='alarmrecord',
                    table='monitor_alarm_record',
                ),
                migrations.AlterModelOptions(
                    name='alarmrecord',
                    options={
                        'managed': False,
                        'verbose_name': '告警记录',
                        'verbose_name_plural': '告警记录',
                        'ordering': ['-timestamp'],
                    },
                ),
                migrations.RemoveIndex(
                    model_name='alarmrecord',
                    name='idx_alarm_rec_branch_tt',
                ),
                migrations.RemoveIndex(
                    model_name='alarmrecord',
                    name='idx_alarm_rec_type',
                ),
                migrations.RemoveIndex(
                    model_name='alarmrecord',
                    name='idx_alarm_rec_status',
                ),
                migrations.RemoveIndex(
                    model_name='alarmrecord',
                    name='idx_alarm_rec_status_tt',
                ),
                migrations.RemoveConstraint(
                    model_name='alarmrecord',
                    name='chk_alarm_rec_branch',
                ),
                migrations.RemoveConstraint(
                    model_name='alarmrecord',
                    name='chk_alarm_rec_type',
                ),
                migrations.RemoveConstraint(
                    model_name='alarmrecord',
                    name='chk_alarm_rec_temperature',
                ),
                migrations.RemoveConstraint(
                    model_name='alarmrecord',
                    name='chk_alarm_rec_area_ratio',
                ),
                migrations.RemoveConstraint(
                    model_name='alarmrecord',
                    name='chk_alarm_rec_warning_level',
                ),
            ],
            database_operations=[],
        ),
    ]
