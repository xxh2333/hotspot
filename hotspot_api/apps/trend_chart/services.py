from datetime import datetime, timedelta

from django.db.models import Avg, Max, Min, Q
from django.db.models.functions import TruncMinute, TruncHour

from apps.logs.models import AlarmLog, SystemConfig
from .models import TemperatureLog, TemperatureDailyStats


class TrendChartService:
    """趋势图表模块业务逻辑层"""

    # ── 常量 ──────────────────────────────────────────────

    RANGE_MAP = {
        '1h': timedelta(hours=1),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
    }

    # ── 实时曲线：初始化数据 ──────────────────────────────

    @staticmethod
    def get_recent_logs(branch=None, duration=600):
        """
        获取最近 N 秒的温度日志数据，用于 SSE init 事件

        Args:
            branch: 支路编号，None 则返回全部
            duration: 回溯时长（秒），默认 600（10 分钟）

        Returns:
            list[dict]: 日志数据列表
        """
        since = datetime.now() - timedelta(seconds=duration)
        qs = TemperatureLog.objects.filter(timestamp__gte=since).order_by('timestamp')
        if branch is not None:
            qs = qs.filter(branch=branch)

        return [
            {
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'branch': log.branch,
                'max_temp': float(log.max_temp),
                'avg_temp': float(log.avg_temp),
                'area_ratio': float(log.area_ratio),
            }
            for log in qs
        ]

    @staticmethod
    def get_latest_log(branch=None):
        """获取最新一条温度日志（update 事件用）"""
        qs = TemperatureLog.objects.order_by('-timestamp')
        if branch is not None:
            qs = qs.filter(branch=branch)
        log = qs.first()
        if log is None:
            return None
        return {
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'branch': log.branch,
            'max_temp': float(log.max_temp),
            'avg_temp': float(log.avg_temp),
            'area_ratio': float(log.area_ratio),
        }

    # ── 历史曲线查询 ──────────────────────────────────────

    @staticmethod
    def get_history(branch, range_value, start_time=None, end_time=None):
        """
        根据时间范围查询聚合后的历史数据

        Args:
            branch: 支路编号 (1~4)
            range_value: 时间范围 (1h / 24h / 7d / 30d)
            start_time: 自定义起始时间（datetime 或 None）
            end_time: 自定义结束时间（datetime 或 None）

        Returns:
            dict: {"range": ..., "aggregation": ..., "branch": ..., "data": [...]}
            或 None 表示无数据
        """
        now = datetime.now()

        # 计算时间区间
        if start_time and end_time:
            t_start, t_end = start_time, end_time
        elif range_value in TrendChartService.RANGE_MAP:
            t_end = now
            t_start = t_end - TrendChartService.RANGE_MAP[range_value]
        else:
            return None

        # 根据 range 选择聚合策略
        if range_value == '1h':
            return TrendChartService._query_raw(branch, t_start, t_end, range_value, 'raw')
        elif range_value == '24h':
            return TrendChartService._query_aggregated(
                branch, t_start, t_end, range_value, '1min', TruncMinute
            )
        elif range_value == '7d':
            return TrendChartService._query_aggregated(
                branch, t_start, t_end, range_value, '1hour', TruncHour
            )
        elif range_value == '30d':
            return TrendChartService._query_daily_stats(branch, t_start, t_end, range_value, '1day')

        return None

    @staticmethod
    def _query_raw(branch, t_start, t_end, range_value, aggregation):
        """1h — 查询原始数据（5 秒间隔）"""
        qs = TemperatureLog.objects.filter(
            branch=branch,
            timestamp__gte=t_start,
            timestamp__lte=t_end,
        ).order_by('timestamp')

        if not qs.exists():
            return None

        data = [
            {
                'time': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'avg_max_temp': float(log.avg_temp),
                'peak_temp': float(log.max_temp),
                'avg_area_ratio': float(log.area_ratio),
                'max_area_ratio': float(log.area_ratio),
            }
            for log in qs
        ]

        return {
            'range': range_value,
            'aggregation': aggregation,
            'branch': branch,
            'data': data,
        }

    @staticmethod
    def _query_aggregated(branch, t_start, t_end, range_value, aggregation, trunc_fn):
        """24h / 7d — 按分钟/小时聚合"""
        qs = (
            TemperatureLog.objects
            .filter(branch=branch, timestamp__gte=t_start, timestamp__lte=t_end)
            .annotate(trunc_time=trunc_fn('timestamp'))
            .values('trunc_time')
            .annotate(
                avg_max_temp=Avg('avg_temp'),
                peak_temp=Max('max_temp'),
                avg_area_ratio=Avg('area_ratio'),
                max_area_ratio=Max('area_ratio'),
            )
            .order_by('trunc_time')
        )

        if not qs:
            return None

        if range_value == '24h':
            time_fmt = '%H:%M'
        else:
            time_fmt = '%m-%d %H:00'

        data = [
            {
                'time': item['trunc_time'].strftime(time_fmt),
                'avg_max_temp': float(item['avg_max_temp']),
                'peak_temp': float(item['peak_temp']),
                'avg_area_ratio': float(item['avg_area_ratio']),
                'max_area_ratio': float(item['max_area_ratio']),
            }
            for item in qs
        ]

        return {
            'range': range_value,
            'aggregation': aggregation,
            'branch': branch,
            'data': data,
        }

    @staticmethod
    def _query_daily_stats(branch, t_start, t_end, range_value, aggregation):
        """30d — 查询日聚合表"""
        qs = TemperatureDailyStats.objects.filter(
            branch=branch,
            stat_date__gte=t_start.date(),
            stat_date__lte=t_end.date(),
        ).order_by('stat_date')

        if not qs.exists():
            return None

        data = [
            {
                'time': item.stat_date.strftime('%Y-%m-%d'),
                'avg_max_temp': float(item.avg_max_temp),
                'peak_temp': float(item.peak_temp),
                'avg_area_ratio': float(item.avg_area_ratio),
                'max_area_ratio': float(item.max_area_ratio),
            }
            for item in qs
        ]

        return {
            'range': range_value,
            'aggregation': aggregation,
            'branch': branch,
            'data': data,
        }

    # ── 告警阈值查询 ──────────────────────────────────────

    DEFAULT_THRESHOLDS = {
        'temperature_threshold': '80.0',
        'area_ratio_threshold': '5.0',
        'temperature_warning_line': '70.0',
        'area_ratio_warning_line': '3.0',
    }

    @staticmethod
    def get_threshold():
        """
        从 system_config 表读取温度与面积告警阈值及预警线

        Returns:
            dict: {"temp_threshold": ..., "area_threshold": ..., "temp_warning_line": ..., ...}
        """
        configs = {
            row['config_key']: row['config_value']
            for row in SystemConfig.objects.filter(
                config_key__in=[
                    'temperature_threshold',
                    'area_ratio_threshold',
                    'temperature_warning_line',
                    'area_ratio_warning_line',
                ]
            ).values('config_key', 'config_value')
        }

        # 取最新更新时间
        latest_updated = SystemConfig.objects.order_by('-updated_at').first()
        updated_at = latest_updated.updated_at.strftime('%Y-%m-%d %H:%M:%S') if latest_updated else None

        return {
            'temp_threshold': float(configs.get('temperature_threshold', TrendChartService.DEFAULT_THRESHOLDS['temperature_threshold'])),
            'area_threshold': float(configs.get('area_ratio_threshold', TrendChartService.DEFAULT_THRESHOLDS['area_ratio_threshold'])),
            'temp_warning_line': float(configs.get('temperature_warning_line', TrendChartService.DEFAULT_THRESHOLDS['temperature_warning_line'])),
            'area_warning_line': float(configs.get('area_ratio_warning_line', TrendChartService.DEFAULT_THRESHOLDS['area_ratio_warning_line'])),
            'updated_at': updated_at,
        }

    # ── 故障告警历史查询 ──────────────────────────────────

    @staticmethod
    def get_alarm_history(branch, range_value, start_time=None, end_time=None):
        """
        查询告警历史记录

        Args:
            branch: 支路编号 (1~4)
            range_value: 时间范围 (1h / 24h / 7d / 30d)
            start_time: 自定义起始时间
            end_time: 自定义结束时间

        Returns:
            dict: {"range": ..., "branch": ..., "data": [...]}
            或 None 表示无数据
        """
        now = datetime.now()

        if start_time and end_time:
            t_start, t_end = start_time, end_time
        elif range_value in TrendChartService.RANGE_MAP:
            t_end = now
            t_start = t_end - TrendChartService.RANGE_MAP[range_value]
        else:
            return None

        qs = AlarmLog.objects.filter(
            branch=branch,
            timestamp__gte=t_start,
            timestamp__lte=t_end,
        ).order_by('-timestamp')

        if not qs.exists():
            return None

        data = [
            {
                'id': alarm.id,
                'timestamp': alarm.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'alarm_level': alarm.alarm_level,
                'alarm_level_text': alarm.get_alarm_level_display(),
                'warning_level': alarm.warning_level,
                'description': alarm.description or '',
                'temperature': float(alarm.temperature),
                'area_ratio': float(alarm.area_ratio),
                'threshold_temp': float(alarm.threshold_temp) if alarm.threshold_temp else None,
                'threshold_area': float(alarm.threshold_area) if alarm.threshold_area else None,
                'auto_trip': alarm.auto_trip,
                'resolution_status': alarm.resolution_status,
                'resolution_status_text': alarm.get_resolution_status_display(),
                'resolved_at': alarm.resolved_at.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if alarm.resolved_at else None,
            }
            for alarm in qs
        ]

        return {
            'range': range_value,
            'branch': branch,
            'data': data,
        }
