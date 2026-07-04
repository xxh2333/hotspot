from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('logs', '0003_maintenancelog_maintenance_created_793f8c_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancelog',
            name='branch',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='故障支路编号'),
        ),
        migrations.AddField(
            model_name='maintenancelog',
            name='fault_date',
            field=models.DateField(default=django.utils.timezone.now, verbose_name='故障日期'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='maintenancelog',
            name='fault_time',
            field=models.TimeField(default=django.utils.timezone.now, verbose_name='故障时间'),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='SystemConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('config_key', models.CharField(max_length=50, unique=True, verbose_name='配置键名')),
                ('config_value', models.CharField(max_length=255, verbose_name='配置值')),
                ('description', models.CharField(blank=True, max_length=255, null=True, verbose_name='配置说明')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                ('updated_by', models.BigIntegerField(blank=True, null=True, verbose_name='最后更新人ID')),
            ],
            options={
                'verbose_name': '系统配置',
                'verbose_name_plural': '系统配置',
                'db_table': 'system_config',
            },
        ),
    ]