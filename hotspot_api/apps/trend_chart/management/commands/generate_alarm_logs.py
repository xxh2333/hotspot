from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from apps.trend_chart.models import TemperatureLog
from apps.logs.models import AlarmLog


class Command(BaseCommand):
    help = '根据温度日志数据生成告警记录'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='扫描过去多少小时的数据')
        parser.add_argument('--temp-threshold', type=float, default=80.0, help='温度阈值（℃）')
        parser.add_argument('--area-threshold', type=float, default=5.0, help='面积阈值（%）')

    def handle(self, *args, **options):
        hours = options['hours']
        temp_threshold = options['temp_threshold']
        area_threshold = options['area_threshold']

        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        logs = TemperatureLog.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time,
        ).order_by('branch', 'timestamp')

        created_count = 0
        skipped_count = 0

        for log in logs:
            max_temp = float(log.max_temp)
            area_ratio = float(log.area_ratio)

            if max_temp >= temp_threshold or area_ratio >= area_threshold:
                alarm_level = 'hot_spot' if max_temp >= temp_threshold else 'over_temp'
                warning_level = 1 if max_temp >= 100 else (2 if max_temp >= 80 else 3)

                existing_alarm = AlarmLog.objects.filter(
                    branch=log.branch,
                    timestamp=log.timestamp,
                ).exists()

                if existing_alarm:
                    skipped_count += 1
                    continue

                description = f"检测到热斑，温度{max_temp:.1f}℃，面积占比{area_ratio:.1f}%"

                AlarmLog.objects.create(
                    timestamp=log.timestamp,
                    branch=log.branch,
                    alarm_level=alarm_level,
                    warning_level=warning_level,
                    description=description,
                    image_path='/mock/images/default.jpg',
                    temperature=log.max_temp,
                    area_ratio=log.area_ratio,
                    threshold_temp=temp_threshold,
                    threshold_area=area_threshold,
                    auto_trip=True,
                    action='trip',
                    resolution_status='pending',
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'成功生成 {created_count} 条告警记录，跳过 {skipped_count} 条重复记录'))