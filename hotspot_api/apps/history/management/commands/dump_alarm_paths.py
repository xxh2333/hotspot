"""诊断命令：查看 monitor_alarm_record 的 image_path 实际值"""
from django.core.management.base import BaseCommand
from apps.history.models import AlarmRecord

class Command(BaseCommand):
    help = '查看 monitor_alarm_record 表中 image_path 的实际值'

    def handle(self, *args, **options):
        for a in AlarmRecord.objects.all():
            self.stdout.write(
                f'id={a.id}  branch={a.branch}  type={a.get_alarm_type_display()}  '
                f'timestamp={a.timestamp}  '
                f'image_path=[{a.image_path}]'
            )
