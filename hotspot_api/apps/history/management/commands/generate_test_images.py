"""
为缺少图片的告警记录生成测试热像图并上传到 OSS
==============================================
用法:
    # 为前 5 条缺少原图的告警记录生成并上传测试图
    python manage.py generate_test_images

    # 指定数量
    python manage.py generate_test_images --count 3

    # 同时生成标注图
    python manage.py generate_test_images --annotated

    # 补传所有缺失图片的告警记录（不限数量）
    python manage.py generate_test_images --all

    # 仅生成图片文件到本地 media 目录，不上传 OSS
    python manage.py generate_test_images --local-only
"""
import os
import struct
import zlib
from io import BytesIO

from django.core.management.base import BaseCommand
from django.utils import timezone

from django.db.models import Q

from apps.history.models import AlarmRecord


def create_test_png(width=256, height=192, color=(220, 60, 30)):
    """
    纯 Python 生成一张纯色 PNG 图片，返回 bytes。
    无需 Pillow，使用 PNG 最小格式。
    """
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + chunk + crc

    # PNG 签名
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR: 宽高、8-bit RGB
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # IDAT: 像素数据 (每行以 filter byte 0 开头)
    raw_rows = b''
    for y in range(height):
        raw_rows += b'\x00'  # filter: None
        for x in range(width):
            # 添加一些变化让图片看起来更像热像图
            r = min(255, color[0] + (x * 30 // width) + (y * 20 // height))
            g = min(255, color[1] + (x * 15 // width))
            b = min(255, color[2] + (y * 10 // height))
            raw_rows += struct.pack('BBB', r, g, b)

    compressed = zlib.compress(raw_rows)
    idat = make_chunk(b'IDAT', compressed)

    # IEND
    iend = make_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


class Command(BaseCommand):
    help = '为缺少图片的告警记录生成测试热像图并上传到 OSS'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=5,
                            help='生成的测试图数量，默认 5')
        parser.add_argument('--annotated', action='store_true',
                            help='同时生成标注图测试数据')
        parser.add_argument('--all', action='store_true',
                            help='补传所有缺失图片的告警记录')
        parser.add_argument('--local-only', action='store_true',
                            help='仅存本地，不上传 OSS')

    def handle(self, *args, **options):
        count = options['count']
        annotated = options['annotated']
        upload_all = options['all']
        local_only = options['local_only']

        # 查询缺少图片的告警记录（空路径 或 非OSS假路径）
        missing_filter = (
            Q(image_path='') | Q(image_path__startswith='/mock') | Q(image_path__startswith='/test') | Q(image_path__startswith='/images/')
        )
        # 如果要求同时生成标注图，把标注图为空的也纳入
        if annotated:
            missing_filter |= (
                Q(annotated_image_path='') | Q(annotated_image_path__isnull=True)
                | Q(annotated_image_path__startswith='/mock') | Q(annotated_image_path__startswith='/test') | Q(annotated_image_path__startswith='/images/')
            )
        qs = AlarmRecord.objects.filter(missing_filter).order_by('-trigger_time')

        if not upload_all:
            qs = qs[:count]

        alarm_list = list(qs)
        if not alarm_list:
            self.stdout.write(self.style.SUCCESS('所有告警记录都已有图片，无需补传。'))
            return

        self.stdout.write(f'准备为 {len(alarm_list)} 条告警记录生成测试图...\n')

        success_count = 0
        for alarm in alarm_list:
            # 判断原图是否需要上传
            need_original = not alarm.image_path or alarm.image_path.startswith(('/mock', '/test', '/images/'))
            need_annotated = annotated and (
                not alarm.annotated_image_path or (alarm.annotated_image_path or '').startswith(('/mock', '/test', '/images/'))
            )

            if not need_original and not need_annotated:
                continue

            # 根据告警类型选择颜色
            if alarm.alarm_type == 1:  # 热斑告警 — 红色
                color = (230, 50, 20)
            elif alarm.alarm_type == 2:  # 温度过载 — 橙色
                color = (240, 120, 20)
            else:  # 设备离线 — 灰色
                color = (100, 100, 100)

            now = timezone.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%Y%m%d_%H%M%S')
            branch = alarm.branch

            # 生成原图 (仅当需要时)
            if need_original:
                image_bytes = create_test_png(width=256, height=192, color=color)
                object_key = f'alarm_images/{branch}/{date_str}/{alarm.id}_{time_str}.png'

                if local_only:
                    # 仅存本地
                    media_root = __import__('django.conf', fromlist=['settings']).settings.MEDIA_ROOT
                    save_dir = os.path.join(media_root, f'alarm_images/{branch}/{date_str}')
                    os.makedirs(save_dir, exist_ok=True)
                    local_path = os.path.join(save_dir, f'{alarm.id}_{time_str}.png')
                    with open(local_path, 'wb') as f:
                        f.write(image_bytes)
                    local_url = f'/media/alarm_images/{branch}/{date_str}/{alarm.id}_{time_str}.png'
                    alarm.image_path = local_url
                    alarm.save(update_fields=['image_path', 'updated_at'])
                    self.stdout.write(f'  [{alarm.id}] 支路{branch} {alarm.get_alarm_type_display()} → 本地 {local_url}')
                else:
                    # 上传到 OSS
                    try:
                        from apps.logs.services import LogService
                        uploaded_key = LogService.upload_to_oss(image_bytes, object_key)
                        alarm.image_path = uploaded_key
                        alarm.save(update_fields=['image_path', 'updated_at'])
                        self.stdout.write(f'  [{alarm.id}] 支路{branch} {alarm.get_alarm_type_display()} → OSS: {uploaded_key}')
                    except ValueError as e:
                        self.stderr.write(f'  [{alarm.id}] OSS 配置错误: {e}')
                        # 回退到本地
                        self.stdout.write(f'  [{alarm.id}] 回退到本地存储...')
                        media_root = __import__('django.conf', fromlist=['settings']).settings.MEDIA_ROOT
                        save_dir = os.path.join(media_root, f'alarm_images/{branch}/{date_str}')
                        os.makedirs(save_dir, exist_ok=True)
                        local_path = os.path.join(save_dir, f'{alarm.id}_{time_str}.png')
                        with open(local_path, 'wb') as f:
                            f.write(image_bytes)
                        local_url = f'/media/alarm_images/{branch}/{date_str}/{alarm.id}_{time_str}.png'
                        alarm.image_path = local_url
                        alarm.save(update_fields=['image_path', 'updated_at'])
                    except RuntimeError as e:
                        self.stderr.write(f'  [{alarm.id}] 上传失败: {e}')
                        continue

                success_count += 1

            # 同时生成标注图
            if need_annotated:
                ann_color = (255, 200, 50)  # 黄色标注
                ann_bytes = create_test_png(width=256, height=192, color=ann_color)
                ann_key = f'alarm_images/{branch}/{date_str}/{alarm.id}_{time_str}_annotated.png'
                try:
                    if local_only:
                        media_root = __import__('django.conf', fromlist=['settings']).settings.MEDIA_ROOT
                        save_dir = os.path.join(media_root, f'alarm_images/{branch}/{date_str}')
                        os.makedirs(save_dir, exist_ok=True)
                        local_path = os.path.join(save_dir, f'{alarm.id}_{time_str}_annotated.png')
                        with open(local_path, 'wb') as f:
                            f.write(ann_bytes)
                        local_url = f'/media/alarm_images/{branch}/{date_str}/{alarm.id}_{time_str}_annotated.png'
                        alarm.annotated_image_path = local_url
                        alarm.save(update_fields=['annotated_image_path', 'updated_at'])
                        self.stdout.write(f'        标注图 → 本地 {local_url}')
                    else:
                        from apps.logs.services import LogService
                        uploaded_ann = LogService.upload_to_oss(ann_bytes, ann_key)
                        alarm.annotated_image_path = uploaded_ann
                        alarm.save(update_fields=['annotated_image_path', 'updated_at'])
                        self.stdout.write(f'        标注图 → OSS: {uploaded_ann}')
                except Exception as e:
                    self.stderr.write(f'        标注图失败: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'\n完成！共为 {success_count} 条告警记录生成/上传了测试图片。'
        ))
