from django.contrib.auth import get_user_model
from apps.logs.models import OperationLog, MaintenanceLog, AlarmLog
from datetime import datetime, date, time

User = get_user_model()

# Create admin user
admin, created = User.objects.get_or_create(
    username='admin',
    defaults={'is_staff': True, 'is_superuser': True}
)
if created:
    admin.set_password('admin123')
    admin.save()
    print('[OK] Created admin user: admin / admin123')
else:
    print('[OK] Admin user already exists (id=%d)' % admin.id)

# Create operator user
operator, created = User.objects.get_or_create(
    username='operator',
    defaults={'is_staff': False}
)
if created:
    operator.set_password('op123')
    operator.save()
    print('[OK] Created operator user: operator / op123')
else:
    print('[OK] Operator user already exists (id=%d)' % operator.id)

# Create alarm log
alarm, created = AlarmLog.objects.get_or_create(
    branch=1,
    alarm_level='hot_spot',
    defaults={
        'timestamp': datetime.now(),
        'image_path': '/test/alarm.jpg',
        'temperature': 85.0,
        'area_ratio': 12.5,
        'threshold_temp': 80.0,
        'threshold_area': 10.0,
        'auto_trip': True,
        'resolution_status': 'pending'
    }
)
if created:
    print('[OK] Created alarm log (id=%d)' % alarm.id)
else:
    print('[OK] Alarm log already exists (id=%d)' % alarm.id)

# Insert operation log
if not OperationLog.objects.filter(user_id=admin.id).exists():
    OperationLog.objects.create(
        user_id=admin.id,
        branch=1,
        action_type='remote_control',
        is_success=True,
        action_detail={'reason': 'test operation'},
        ip_address='127.0.0.1'
    )
    print('[OK] Inserted operation log')
else:
    print('[OK] Operation log already exists')

# Insert maintenance log
if not MaintenanceLog.objects.filter(user_id=admin.id).exists():
    MaintenanceLog.objects.create(
        alarm_id=alarm.id,
        user_id=admin.id,
        fault_date=date.today(),
        fault_time=time(10, 0, 0),
        branch=1,
        fault_device='fuse',
        repair_detail='test repair record',
        repair_images=['/test/repair.jpg']
    )
    print('[OK] Inserted maintenance log')
else:
    print('[OK] Maintenance log already exists')

print('[DONE] Test data preparation complete!')
