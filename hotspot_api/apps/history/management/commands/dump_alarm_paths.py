"""诊断命令：查看 alarm_records 的 image_path 实际值"""
from django.core.management.base import BaseCommand
from apps.history.models import AlarmRecord

class Command(BaseCommand):
    help = '查看 alarm_records 表中 image_path 的实际值'

    def handle(self, *args, **options):
        for a in AlarmRecord.objects.all():
            self.stdout.write(
                f'id={a.id}  branch={a.branch}  type={a.get_alarm_type_display()}  '
                f'trigger_time={a.trigger_time}  '
                f'image_path=[{a.image_path}]  '
                f'ann_path=[{a.annotated_image_path or "NULL"}]'
            )
