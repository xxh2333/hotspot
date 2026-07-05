"""
告警查询 500 诊断脚本
"""
import os, sys, traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotspot_api.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import django
django.setup()

from apps.history.models import AlarmRecord
from apps.logs.models import MaintenanceLog
from datetime import datetime

print('=== 1. 查 alarm_records 表 ===')
try:
    qs = AlarmRecord.objects.filter(
        trigger_time__gte=datetime(2026,1,1),
        trigger_time__lte=datetime(2026,7,5)
    )
    count = qs.count()
    print(f'OK: 找到 {count} 条记录')
except Exception as e:
    traceback.print_exc()

print()
print('=== 2. 查 maintenance_logs 表 ===')
try:
    qs = MaintenanceLog.objects.all()
    cnt = qs.count()
    print(f'OK: {cnt} 条记录')
    if cnt > 0:
        first = qs.first()
        print(f'字段存在: fault_date={hasattr(first, "fault_date")}, fault_time={hasattr(first, "fault_time")}, branch={hasattr(first, "branch")}')
        print(f'字段值: fault_date={first.fault_date}, fault_time={first.fault_time}, branch={first.branch}')
except Exception as e:
    traceback.print_exc()

print()
print('=== 3. 模拟告警查询完整流程 ===')
try:
    from apps.history.serializers import AlarmRecordSerializer
    qs = AlarmRecord.objects.filter(
        trigger_time__gte=datetime(2026,1,1),
        trigger_time__lte=datetime(2026,7,5)
    ).order_by('-trigger_time')[:5]
    alarm_ids = [obj.id for obj in qs]
    print(f'alarm_ids: {alarm_ids}')
    maint_map = {}
    if alarm_ids:
        maintenances = MaintenanceLog.objects.filter(alarm_id__in=alarm_ids)
        maint_map = {m.alarm_id: m for m in maintenances}
        print(f'maintenance_map: {len(maint_map)} 条')
        for m in maintenances:
            print(f'  id={m.id}, alarm_id={m.alarm_id}, repair_images={m.repair_images}')
    else:
        print('alarm_records 表为空，只测序列化')
    serializer = AlarmRecordSerializer(qs, many=True, context={'maintenance_map': maint_map})
    data = serializer.data
    print(f'序列化成功: {len(data)} 条')
except Exception as e:
    traceback.print_exc()

print()
print('=== 诊断完成 ===')