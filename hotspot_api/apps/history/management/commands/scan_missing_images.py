"""
扫描缺失的告警图片记录并支持单条补录
=========================================
用法:
    # 列出所有 image_path 为空的告警记录
    python manage.py scan_missing_images

    # 列出所有 image_path 为空或 annotated_image_path 为空的记录
    python manage.py scan_missing_images --type all

    # 仅扫描标注图为空的记录
    python manage.py scan_missing_images --type annotated

    # 限制扫描数量
    python manage.py scan_missing_images --limit 50

    # 同时显示已处理的告警记录
    python manage.py scan_missing_images --show-resolved

    # 为指定告警记录补录图片
    python manage.py scan_missing_images --alarm-id 42 --image-file /path/to/image.jpg

    # 补录标注图
    python manage.py scan_missing_images --alarm-id 42 --image-file /path/to/ann.jpg --type annotated
"""
import os

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.history.models import AlarmRecord


class Command(BaseCommand):
    help = '扫描缺失的告警图片记录并支持单条补录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type', type=str, default='original',
            choices=['original', 'annotated', 'all'],
            help='检查的图片类型: original(原图), annotated(标注图), all(全部)',
        )
        parser.add_argument(
            '--alarm-id', type=int, default=None,
            help='为指定告警 ID 补录图片（需配合 --image-file）',
        )
        parser.add_argument(
            '--image-file', type=str, default=None,
            help='要上传的图片文件路径',
        )
        parser.add_argument(
            '--limit', type=int, default=200,
            help='最多展示的记录数，默认 200',
        )
        parser.add_argument(
            '--show-resolved', action='store_true',
            help='同时显示已处理的告警记录（默认只显示未处理的）',
        )

    def handle(self, *args, **options):
        image_type = options['type']
        alarm_id = options['alarm_id']
        image_file = options['image_file']
        limit = options['limit']

        # ---- 补录模式 ----
        if alarm_id is not None:
            self._backfill_single(alarm_id, image_file, image_type)
            return

        # ---- 扫描模式 ----
        self._scan_missing(image_type, limit, options['show_resolved'])

    def _scan_missing(self, image_type, limit, show_resolved):
        """扫描 image_path 为空的告警记录"""
        qs = AlarmRecord.objects.all()

        if not show_resolved:
            qs = qs.filter(resolution_status='pending')

        if image_type == 'original':
            qs = qs.filter(
                Q(image_path='') | Q(image_path__isnull=True)
                | Q(image_path__startswith='/mock') | Q(image_path__startswith='/test')
            )
            self.stdout.write('\n--- image_path 为空的告警记录 ---')
        elif image_type == 'annotated':
            qs = qs.filter(
                Q(annotated_image_path='') | Q(annotated_image_path__isnull=True)
                | Q(annotated_image_path__startswith='/mock') | Q(annotated_image_path__startswith='/test')
            )
            self.stdout.write('\n--- annotated_image_path 为空的告警记录 ---')
        else:  # all
            qs = qs.filter(
                Q(image_path='') | Q(image_path__isnull=True)
                | Q(image_path__startswith='/mock') | Q(image_path__startswith='/test')
                | Q(annotated_image_path='') | Q(annotated_image_path__isnull=True)
                | Q(annotated_image_path__startswith='/mock') | Q(annotated_image_path__startswith='/test')
            )

        total = qs.count()
        self.stdout.write(f'共 {total} 条记录\n')

        if total == 0:
            self.stdout.write('没有缺失图片的告警记录。')
            return

        qs = qs.order_by('-trigger_time')[:limit]

        # 表头
        self.stdout.write(
            f'{"ID":>6}  {"支路":>4}  {"告警类型":>14}  {"触发时间":>22}  '
            f'{"原图":>6}  {"标注图":>6}  {"状态":>8}'
        )
        self.stdout.write('-' * 80)

        # 数据行
        for record in qs:
            has_original = 'OK' if record.image_path else 'MISS'
            has_annotated = 'OK' if record.annotated_image_path else 'MISS'
            alarm_type_display = record.get_alarm_type_display()
            self.stdout.write(
                f'{record.id:>6}  {record.branch:>4}  '
                f'{alarm_type_display:>14}  '
                f'{record.trigger_time.strftime("%Y-%m-%d %H:%M:%S"):>22}  '
                f'{has_original:>6}  {has_annotated:>6}  '
                f'{record.get_resolution_status_display():>8}'
            )

        if total > limit:
            self.stdout.write(f'\n... 仅显示前 {limit} 条，共 {total} 条记录。使用 --limit 调整显示数量。')

    def _backfill_single(self, alarm_id, image_file, image_type):
        """为单条告警记录补录图片并上传到 OSS"""
        if not image_file:
            self.stderr.write('错误: --image-file 参数为必填项')
            return

        try:
            alarm = AlarmRecord.objects.get(pk=alarm_id)
        except AlarmRecord.DoesNotExist:
            self.stderr.write(f'错误: 告警记录 {alarm_id} 不存在')
            return

        # 读取文件
        try:
            with open(image_file, 'rb') as f:
                image_bytes = f.read()
        except FileNotFoundError:
            self.stderr.write(f'错误: 图片文件不存在: {image_file}')
            return

        # 文件校验
        ext = os.path.splitext(image_file)[1].lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
            self.stderr.write(f'错误: 不支持的图片格式 {ext}，仅支持 jpg/png/webp')
            return

        # 生成 OSS key
        now = timezone.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%Y%m%d_%H%M%S')
        suffix = '_annotated' if image_type == 'annotated' else ''
        object_key = f'alarm_images/{alarm.branch}/{date_str}/{alarm_id}_{time_str}{suffix}{ext}'

        # 上传到 OSS
        try:
            from apps.logs.services import LogService
            uploaded_key = LogService.upload_to_oss(image_bytes, object_key)
        except ValueError as e:
            self.stderr.write(f'OSS 配置错误: {e}')
            return
        except RuntimeError as e:
            self.stderr.write(f'OSS 上传失败: {e}')
            return

        # 更新数据库
        if image_type == 'annotated':
            alarm.annotated_image_path = uploaded_key
            alarm.save(update_fields=['annotated_image_path', 'updated_at'])
        else:
            alarm.image_path = uploaded_key
            alarm.save(update_fields=['image_path', 'updated_at'])

        self.stdout.write(self.style.SUCCESS(
            f'成功: 告警 {alarm_id} 的 {image_type}_image_path 已更新为 {uploaded_key}'
        ))
