import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from apps.trend_chart.models import TemperatureLog


class Command(BaseCommand):
    help = '生成温度日志模拟数据'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='生成过去多少小时的数据')
        parser.add_argument('--interval', type=int, default=5, help='数据间隔（秒）')
        parser.add_argument('--branch', type=int, default=0, help='支路编号（0表示全部4个支路）')

    def handle(self, *args, **options):
        hours = options['hours']
        interval = options['interval']
        branch = options['branch']

        branches = [branch] if branch != 0 else [1, 2, 3, 4]
        now = datetime.now()
        start_time = now - timedelta(hours=hours)

        total_records = 0
        records_per_branch = int((hours * 3600) / interval)

        for b in branches:
            base_temp = random.uniform(35, 50)
            temp_variation = random.uniform(5, 15)
            hotspot_probability = 0.02

            for i in range(records_per_branch):
                timestamp = start_time + timedelta(seconds=i * interval)

                is_hotspot = random.random() < hotspot_probability

                if is_hotspot:
                    max_temp = random.uniform(75, 120)
                    min_temp = random.uniform(40, 60)
                    avg_temp = random.uniform(50, 70)
                    area_ratio = random.uniform(3, 30)
                    hotspot_count = random.randint(1, 5)
                else:
                    temp_offset = random.uniform(-temp_variation, temp_variation)
                    max_temp = base_temp + temp_offset + random.uniform(0, 5)
                    min_temp = base_temp + temp_offset - random.uniform(0, 5)
                    avg_temp = base_temp + temp_offset
                    area_ratio = random.uniform(0, 3)
                    hotspot_count = 0

                try:
                    TemperatureLog.objects.create(
                        timestamp=timestamp,
                        branch=b,
                        max_temp=round(max_temp, 2),
                        min_temp=round(min_temp, 2),
                        avg_temp=round(avg_temp, 2),
                        area_ratio=round(area_ratio, 2),
                        hotspot_count=hotspot_count,
                    )
                    total_records += 1
                except Exception:
                    pass

        self.stdout.write(self.style.SUCCESS(f'成功生成 {total_records} 条温度日志数据'))