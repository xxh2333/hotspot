import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotspot_api.settings')
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

import django
django.setup()

from django.conf import settings
print('=== 数据库连接 ===')
print(f'  HOST: {settings.DATABASES["default"]["HOST"]}')
print(f'  PORT: {settings.DATABASES["default"]["PORT"]}')
print(f'  NAME: {settings.DATABASES["default"]["NAME"]}')
print(f'  USER: {settings.DATABASES["default"]["USER"]}')

from apps.history.models import TemperatureRecord, AlarmRecord
print()
print('=== 模型映射 ===')
print(f'  TemperatureRecord → 表: {TemperatureRecord._meta.db_table}')
print(f'  AlarmRecord → 表: {AlarmRecord._meta.db_table}')
print(f'  managed: {TemperatureRecord._meta.managed}')

print()
print('=== 数据量 ===')
try:
    t_count = TemperatureRecord.objects.count()
    print(f'  TemperatureRecord: {t_count} 条')
except Exception as e:
    print(f'  TemperatureRecord 查询失败: {e}')

try:
    a_count = AlarmRecord.objects.count()
    print(f'  AlarmRecord: {a_count} 条')
except Exception as e:
    print(f'  AlarmRecord 查询失败: {e}')

# 对比 monitor 模块的模型
from apps.monitor.models import TemperatureRecord as MonTemp, AlarmRecord as MonAlarm
print()
print('=== monitor 模块数据量（相同表） ===')
try:
    mt_count = MonTemp.objects.count()
    print(f'  monitor.TemperatureRecord: {mt_count} 条')
except Exception as e:
    print(f'  monitor.TemperatureRecord 查询失败: {e}')

try:
    ma_count = MonAlarm.objects.count()
    print(f'  monitor.AlarmRecord: {ma_count} 条')
except Exception as e:
    print(f'  monitor.AlarmRecord 查询失败: {e}')

print()
print('=== 最新一条温度记录 ===')
try:
    t = TemperatureRecord.objects.order_by('-timestamp').first()
    if t:
        print(f'  id={t.id} branch={t.branch} timestamp={t.timestamp} max_temp={t.max_temp}')
    else:
        print('  （空）')
except Exception as e:
    print(f'  查询失败: {e}')

print()
print('=== 最新一条告警记录 ===')
try:
    a = AlarmRecord.objects.order_by('-timestamp').first()
    if a:
        print(f'  id={a.id} branch={a.branch} timestamp={a.timestamp} alarm_type={a.alarm_type}')
    else:
        print('  （空）')
except Exception as e:
    print(f'  查询失败: {e}')
