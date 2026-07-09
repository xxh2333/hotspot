"""
monitor 业务服务层
------------------
- SSEManager: SSE 客户端连接管理，支持 status / alarm / image 三类事件广播
- DashboardService: 仪表盘数据聚合、温度统计、设备状态
- AlarmService: 告警触发、阈值判断、告警查询
- ControlService: 控制指令处理（复位/分闸/阈值修改）
"""
import json
import logging
import threading
from datetime import date, datetime, timedelta
from typing import Optional

from django.db.models import Avg, Max, Min, Count, Q
from django.utils import timezone
from django.conf import settings

from .models import (
    BranchStatus, TemperatureRecord, AlarmRecord,
    SystemConfig, DeviceStatus, ThermalImage,
)

logger = logging.getLogger('monitor')


# ============================================================================
# SSE 连接管理器
# ============================================================================

class SSEManager:
    """
    SSE 客户端连接管理器（单例）
    管理所有 SSE 客户端连接，支持按事件类型广播消息
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._clients = {}
                    cls._instance._client_lock = threading.Lock()
        return cls._instance

    def register(self, client_id: str, queue):
        """注册 SSE 客户端"""
        with self._client_lock:
            self._clients[client_id] = queue
            logger.info(f'SSE 客户端注册: {client_id}, 当前连接数: {len(self._clients)}')

    def unregister(self, client_id: str):
        """注销 SSE 客户端"""
        with self._client_lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f'SSE 客户端断开: {client_id}, 当前连接数: {len(self._clients)}')

    def broadcast(self, event: str, data: str):
        """向所有已连接的客户端广播事件"""
        with self._client_lock:
            dead_clients = []
            for client_id, queue in self._clients.items():
                try:
                    queue.put({'event': event, 'data': data})
                except Exception:
                    dead_clients.append(client_id)
            # 清理已断开的客户端
            for client_id in dead_clients:
                del self._clients[client_id]

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        with self._client_lock:
            return len(self._clients)


# 全局单例
sse_manager = SSEManager()


# ============================================================================
# 阈值服务
# ============================================================================

class ThresholdService:
    """告警阈值读取与更新"""

    @staticmethod
    def get_thresholds() -> dict:
        """获取当前温度阈值和面积阈值"""
        defaults = {'temperature': 80.0, 'area_ratio': 5.0}
        try:
            temp_cfg = SystemConfig.objects.filter(config_key='temperature_threshold').first()
            area_cfg = SystemConfig.objects.filter(config_key='area_ratio_threshold').first()
            return {
                'temperature': float(temp_cfg.config_value) if temp_cfg else defaults['temperature'],
                'area_ratio': float(area_cfg.config_value) if area_cfg else defaults['area_ratio'],
            }
        except Exception as e:
            logger.warning(f'读取阈值失败，使用默认值: {e}')
            return defaults

    @staticmethod
    def set_thresholds(temperature: float, area_ratio: float) -> dict:
        """更新告警阈值"""
        temp_cfg, _ = SystemConfig.objects.update_or_create(
            config_key='temperature_threshold',
            defaults={'config_value': str(temperature), 'description': '温度告警阈值(℃)'},
        )
        area_cfg, _ = SystemConfig.objects.update_or_create(
            config_key='area_ratio_threshold',
            defaults={'config_value': str(area_ratio), 'description': '面积告警阈值(%)'},
        )
        return {
            'temperature': float(temp_cfg.config_value),
            'area_ratio': float(area_cfg.config_value),
            'effective_at': timezone.localtime(timezone.now()).isoformat(),
        }


# ============================================================================
# 仪表盘服务
# ============================================================================

class DashboardService:
    """仪表盘数据聚合服务"""

    @staticmethod
    def get_initial_data() -> dict:
        """
        获取仪表盘初始数据（页面加载时调用）
        包含：各支路状态、全局统计、告警统计、设备状态、阈值
        """
        now = timezone.localtime(timezone.now())
        today = now.date()

        # 1. 各支路最新状态
        branches_qs = BranchStatus.objects.all().order_by('branch')
        branches_data = []
        global_temps = []

        for bs in branches_qs:
            branches_data.append({
                'id': bs.branch,
                'temperature': bs.temperature,
                'area_ratio': bs.area_ratio,
                'breaker_status': bs.breaker_status,
                'alarm_status': bs.alarm_status,
                'updated_at': bs.updated_at.isoformat(),
            })
            global_temps.append(bs.temperature)

        # 如果数据库还没有支路数据，初始化4个空支路
        existing_branches = {b['id'] for b in branches_data}
        for bid in range(1, 5):
            if bid not in existing_branches:
                bs, _ = BranchStatus.objects.get_or_create(
                    branch=bid,
                    defaults={'temperature': 0.0, 'area_ratio': 0.0, 'breaker_status': 'closed', 'alarm_status': 'normal'},
                )
                branches_data.append({
                    'id': bs.branch,
                    'temperature': bs.temperature,
                    'area_ratio': bs.area_ratio,
                    'breaker_status': bs.breaker_status,
                    'alarm_status': bs.alarm_status,
                    'updated_at': bs.updated_at.isoformat(),
                })
                global_temps.append(bs.temperature)

        branches_data.sort(key=lambda x: x['id'])

        # 2. 全局温度统计
        if global_temps:
            max_temp = max(global_temps)
            min_temp = min(global_temps)
            avg_temp = round(sum(global_temps) / len(global_temps), 1)
            max_branch = next((b['id'] for b in branches_data if b['temperature'] == max_temp), 1)
            min_branch = next((b['id'] for b in branches_data if b['temperature'] == min_temp), 1)
        else:
            max_temp = min_temp = avg_temp = 0.0
            max_branch = min_branch = 1

        global_data = {
            'max_temp': max_temp,
            'min_temp': min_temp,
            'avg_temp': avg_temp,
            'max_temp_branch': max_branch,
            'min_temp_branch': min_branch,
        }

        # 3. 当日告警统计
        today_start = timezone.make_aware(
            datetime.combine(today, datetime.min.time())
        )
        today_alarms = AlarmRecord.objects.filter(timestamp__gte=today_start)
        alarm_stats = {
            'date': today.isoformat(),
            'total': today_alarms.count(),
            'breakdown': {
                'hot_spot': today_alarms.filter(alarm_type='hot_spot').count(),
                'over_temp': today_alarms.filter(alarm_type='over_temp').count(),
                'offline': today_alarms.filter(alarm_type='offline').count(),
            },
            'unresolved': today_alarms.filter(status='pending').count(),
        }

        # 4. 设备状态
        devices_qs = DeviceStatus.objects.filter(
            device_type__in=['thermal_camera', 'raspberrypi']
        )
        total_devices = devices_qs.count() or 1
        online_devices = devices_qs.filter(status='online').count()
        offline_list = list(
            devices_qs.filter(status='offline').values_list('device_id', flat=True)
        )

        devices_data = {
            'total': max(total_devices, 4) if total_devices else 4,
            'online': online_devices,
            'offline_list': offline_list,
        }

        # 5. 热像仪状态
        camera = DeviceStatus.objects.filter(device_type='thermal_camera').first()
        thermal_camera = {
            'status': camera.status if camera else 'online',
            'fps': camera.extra_info.get('fps', 1.0) if camera else 1.0,
        }

        # 6. MQTT 状态
        mqtt = DeviceStatus.objects.filter(device_type='mqtt').first()
        mqtt_data = {
            'status': mqtt.status if mqtt else 'connected',
        }

        # 7. 阈值
        thresholds = ThresholdService.get_thresholds()

        return {
            'timestamp': now.isoformat(),
            'branches': branches_data,
            'global': global_data,
            'alarm_statistics': alarm_stats,
            'devices': devices_data,
            'thermal_camera': thermal_camera,
            'mqtt': mqtt_data,
            'thresholds': thresholds,
        }

    @staticmethod
    def get_realtime_status() -> dict:
        """
        获取实时状态数据（SSE status 事件用）
        包含：各支路温度/状态、全局统计、设备状态
        """
        now = timezone.localtime(timezone.now())
        branches_qs = BranchStatus.objects.all().order_by('branch')
        branches_data = []
        temps = []

        for bs in branches_qs:
            branches_data.append({
                'id': bs.branch,
                'temperature': bs.temperature,
                'area_ratio': bs.area_ratio,
                'breaker_status': bs.breaker_status,
                'alarm_status': bs.alarm_status,
            })
            temps.append(bs.temperature)

        if temps:
            max_temp = max(temps)
            min_temp = min(temps)
            max_branch = next(
                (i + 1 for i, t in enumerate(temps) if t == max_temp), 1
            )
            min_branch = next(
                (i + 1 for i, t in enumerate(temps) if t == min_temp), 1
            )
        else:
            max_temp = min_temp = 0.0
            max_branch = min_branch = 1

        camera = DeviceStatus.objects.filter(device_type='thermal_camera').first()
        mqtt = DeviceStatus.objects.filter(device_type='mqtt').first()

        return {
            'timestamp': now.isoformat(),
            'branches': branches_data,
            'global': {
                'max_temp': max_temp,
                'min_temp': min_temp,
                'max_temp_branch': max_branch,
                'min_temp_branch': min_branch,
            },
            'devices': {
                'thermal_camera': camera.status if camera else 'online',
                'mqtt': mqtt.status if mqtt else 'connected',
            },
        }


# ============================================================================
# 温度历史服务
# ============================================================================

class TemperatureHistoryService:
    """温度历史数据服务"""

    @staticmethod
    def get_history(branch: int, start: str, end: str, interval: str = 'hour') -> dict:
        """
        查询指定时间范围的温度历史数据

        参数:
            branch: 支路编号 1~4
            start: 开始时间字符串 "YYYY-MM-DD HH:MM:SS"
            end: 结束时间字符串 "YYYY-MM-DD HH:MM:SS"
            interval: 聚合粒度 hour / day
        """
        try:
            start_dt = timezone.make_aware(
                datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
            )
            end_dt = timezone.make_aware(
                datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
            )
        except ValueError as e:
            raise ValueError(f'时间格式错误，应为 YYYY-MM-DD HH:MM:SS: {e}')

        records = TemperatureRecord.objects.filter(
            branch=branch,
            timestamp__gte=start_dt,
            timestamp__lte=end_dt,
        ).order_by('timestamp')

        series = []
        for r in records:
            local_ts = timezone.localtime(r.timestamp)
            time_fmt = '%H:%M' if interval == 'hour' else '%m-%d'
            series.append({
                'time': local_ts.strftime(time_fmt),
                'max_temp': r.max_temp,
                'avg_temp': r.avg_temp,
            })

        return {
            'branch': branch,
            'start': start,
            'end': end,
            'interval': interval,
            'series': series,
        }

    @staticmethod
    def aggregate_and_store(branch: int, temperature: float, area_ratio: float, ts: datetime = None):
        """
        存储温度记录（由 MQTT 数据采集触发）
        每5秒采集一次，按小时聚合存储
        """
        if ts is None:
            ts = timezone.now()

        local_ts = timezone.localtime(ts)
        # 按小时对齐
        hour_slot = local_ts.replace(minute=0, second=0, microsecond=0)

        existing = TemperatureRecord.objects.filter(
            branch=branch,
            timestamp=hour_slot,
        ).first()

        if existing:
            # 更新该小时的 max/avg
            existing.max_temp = max(existing.max_temp, temperature)
            # 使用采样计数来纠正平均值
            count = existing.sample_count
            total_temp = existing.avg_temp * count + temperature
            new_count = count + 1
            existing.avg_temp = round(total_temp / new_count, 1)
            existing.sample_count = new_count
            existing.area_ratio = max(existing.area_ratio, area_ratio)
            existing.save(update_fields=['max_temp', 'avg_temp', 'area_ratio', 'sample_count'])
        else:
            TemperatureRecord.objects.create(
                branch=branch,
                timestamp=hour_slot,
                max_temp=temperature,
                avg_temp=temperature,
                area_ratio=area_ratio,
                sample_count=1,
            )


# ============================================================================
# 告警服务
# ============================================================================

class AlarmService:
    """告警判断、记录与查询"""

    @staticmethod
    def get_history(
        page: int = 1, limit: int = 20,
        branch: Optional[int] = None,
        alarm_type: Optional[str] = None,
        status: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict:
        """查询历史告警列表，支持分页和多条件筛选"""
        qs = AlarmRecord.objects.all()

        if branch:
            qs = qs.filter(branch=branch)
        if alarm_type:
            qs = qs.filter(alarm_type=alarm_type)
        if status:
            qs = qs.filter(status=status)
        if start:
            try:
                start_dt = timezone.make_aware(datetime.strptime(start, '%Y-%m-%d %H:%M:%S'))
                qs = qs.filter(timestamp__gte=start_dt)
            except ValueError:
                pass
        if end:
            try:
                end_dt = timezone.make_aware(datetime.strptime(end, '%Y-%m-%d %H:%M:%S'))
                qs = qs.filter(timestamp__lte=end_dt)
            except ValueError:
                pass

        total = qs.count()
        offset = (page - 1) * limit
        records = qs[offset:offset + limit]

        list_data = []
        for r in records:
            list_data.append({
                'id': r.id,
                'timestamp': timezone.localtime(r.timestamp).isoformat(),
                'branch': r.branch,
                'alarm_type': r.alarm_type,
                'temperature': r.temperature,
                'area_ratio': r.area_ratio,
                'status': r.status,
                'image_path': r.image_path,
            })

        return {
            'total': total,
            'page': page,
            'limit': limit,
            'list': list_data,
        }

    @staticmethod
    def check_and_trigger(branch: int, temperature: float, area_ratio: float, image_path: str = None) -> Optional[dict]:
        """
        检查是否触发告警，若触发则创建告警记录并返回告警数据

        阈值来自 system_config 表
        """
        thresholds = ThresholdService.get_thresholds()
        temp_threshold = thresholds['temperature']
        area_threshold = thresholds['area_ratio']

        alarm_type = None
        description = None

        if area_ratio >= area_threshold:
            alarm_type = 'hot_spot'
            description = f'{branch}号光伏板热斑面积达{area_ratio}%，最高温度{temperature}℃'
        elif temperature >= temp_threshold:
            alarm_type = 'over_temp'
            description = f'{branch}号光伏板温度过载，最高温度{temperature}℃'

        if alarm_type is None:
            return None

        # 检查是否已有未处理的同类型告警（避免重复告警）
        recent_alarm = AlarmRecord.objects.filter(
            branch=branch,
            alarm_type=alarm_type,
            status='pending',
            timestamp__gte=timezone.now() - timedelta(minutes=5),
        ).first()

        if recent_alarm:
            # 更新已有告警的温度/面积数据
            recent_alarm.temperature = temperature
            recent_alarm.area_ratio = area_ratio
            recent_alarm.save(update_fields=['temperature', 'area_ratio'])
            return None

        now = timezone.now()
        auto_trip = alarm_type == 'hot_spot'  # 热斑告警自动分闸

        # 如果没有传入 image_path，尝试关联最近的红外热像图
        if not image_path:
            recent_image = ThermalImage.objects.filter(
                timestamp__gte=now - timedelta(seconds=60),
            ).exclude(
                image_path='',
            ).order_by('-timestamp').first()

            if recent_image:
                image_path = recent_image.image_path
                logger.info(
                    f'告警 {alarm_type} 关联图像: {image_path} '
                    f'(ThermalImage id={recent_image.id})'
                )

        alarm = AlarmRecord.objects.create(
            branch=branch,
            alarm_type=alarm_type,
            temperature=temperature,
            area_ratio=area_ratio,
            status='pending',
            image_path=image_path or '',
            description=description,
            auto_trip=auto_trip,
            timestamp=now,
        )

        # 更新支路告警状态
        BranchStatus.objects.filter(branch=branch).update(alarm_status='alarm')

        return {
            'timestamp': timezone.localtime(now).isoformat(),
            'alarm_id': alarm.id,
            'branch': branch,
            'alarm_type': alarm_type,
            'temperature': temperature,
            'area_ratio': area_ratio,
            'auto_trip': auto_trip,
            'image_path': image_path or '',
            'description': description,
        }


# ============================================================================
# 控制服务
# ============================================================================

class ControlService:
    """控制指令处理服务"""

    @staticmethod
    def send_reset(branch: int, operator: str = 'admin') -> dict:
        """
        发送复位（合闸）指令
        通过 MQTT 下发到树莓派执行
        """
        # 校验支路
        if branch not in range(1, 5):
            raise ValueError('支路编号无效，有效值为 1~4')

        # 检查 MQTT 连接状态
        mqtt_device = DeviceStatus.objects.filter(device_type='mqtt').first()
        if mqtt_device and mqtt_device.status == 'offline':
            raise ConnectionError('MQTT 服务不可用')

        # 发布 MQTT 消息（由 mqtt.py 的客户端执行实际发送）
        from .mqtt import mqtt_client
        if not mqtt_client.is_connected():
            raise ConnectionError('MQTT 服务不可用')

        payload = {
            'command': 'reset',
            'branch': branch,
            'timestamp': timezone.localtime(timezone.now()).isoformat(),
            'operator': operator,
        }
        mqtt_client.publish_control(payload)

        # 更新支路断路器状态
        BranchStatus.objects.filter(branch=branch).update(breaker_status='closed')

        return {
            'branch': branch,
            'command': 'reset',
            'status': 'sent',
        }

    @staticmethod
    def send_trip(branch: int, operator: str = 'admin', reason: str = '人工远程分闸') -> dict:
        """
        发送分闸指令
        """
        if branch not in range(1, 5):
            raise ValueError('支路编号无效，有效值为 1~4')

        from .mqtt import mqtt_client
        if not mqtt_client.is_connected():
            raise ConnectionError('MQTT 服务不可用')

        payload = {
            'command': 'trip',
            'branch': branch,
            'timestamp': timezone.localtime(timezone.now()).isoformat(),
            'operator': operator,
            'reason': reason,
        }
        mqtt_client.publish_control(payload)

        # 更新支路断路器状态
        BranchStatus.objects.filter(branch=branch).update(breaker_status='open')

        return {
            'branch': branch,
            'command': 'trip',
            'status': 'sent',
        }


# ============================================================================
# MQTT 数据处理服务
# ============================================================================

class MQTTDataProcessor:
    """
    MQTT 上行数据处理
    接收树莓派上报的温度/状态数据和红外图像帧
    """

    @staticmethod
    def process_status(data: dict):
        """
        处理温度/状态数据 (topic: pv/hotspot/up/status)

        数据格式:
        {
            "timestamp": "2026-07-02T14:35:17+08:00",
            "device_id": "raspberrypi-01",
            "branches": [...],
            "breaker_status": {...},
            "thermal_camera": "online"
        }
        """
        device_id = data.get('device_id', 'raspberrypi-01')
        branches = data.get('branches', [])
        breaker_status = data.get('breaker_status', {})
        thermal_camera_status = data.get('thermal_camera', 'online')
        timestamp_str = data.get('timestamp')

        # 解析时间戳
        if timestamp_str:
            try:
                ts = datetime.fromisoformat(timestamp_str)
                if timezone.is_naive(ts):
                    ts = timezone.make_aware(ts)
            except (ValueError, TypeError):
                ts = timezone.now()
        else:
            ts = timezone.now()

        # 更新各支路状态
        for branch_data in branches:
            bid = branch_data.get('id')
            if bid is None:
                continue

            breaker = breaker_status.get(str(bid), 'closed')
            temp = branch_data.get('temperature', 0.0)
            area = branch_data.get('area_ratio', 0.0)

            obj, created = BranchStatus.objects.update_or_create(
                branch=bid,
                defaults={
                    'temperature': temp,
                    'area_ratio': area,
                    'breaker_status': breaker,
                }
            )

            # 存储温度历史记录
            TemperatureHistoryService.aggregate_and_store(bid, temp, area, ts)

            # 告警检测
            alarm_data = AlarmService.check_and_trigger(bid, temp, area)
            if alarm_data:
                # 通过 SSE 广播告警
                sse_manager.broadcast('alarm', json.dumps(alarm_data, ensure_ascii=False))

        # 更新设备状态
        DeviceStatus.objects.update_or_create(
            device_type='thermal_camera',
            device_id=device_id,
            defaults={'status': thermal_camera_status},
        )
        DeviceStatus.objects.update_or_create(
            device_type='raspberrypi',
            device_id=device_id,
            defaults={'status': 'online'},
        )
        DeviceStatus.objects.update_or_create(
            device_type='mqtt',
            device_id='default',
            defaults={'status': 'connected'},
        )

        # 通过 SSE 广播实时状态
        status_data = DashboardService.get_realtime_status()
        sse_manager.broadcast('status', json.dumps(status_data, ensure_ascii=False))

    @staticmethod
    def process_image(data: dict):
        """
        处理红外图像帧 (topic: pv/hotspot/up/image)

        数据格式:
        {
            "timestamp": "2026-07-02T14:35:18+08:00",
            "device_id": "raspberrypi-01",
            "image": "base64_encoded_image_data",
            "annotated_image": "base64_encoded_image_data",
            "width": 256,
            "height": 192,
            "hotspots": [...]
        }
        """
        device_id = data.get('device_id', 'raspberrypi-01')
        timestamp_str = data.get('timestamp')
        image_b64 = data.get('image', '')
        annotated_b64 = data.get('annotated_image', '')
        width = data.get('width', 256)
        height = data.get('height', 192)
        hotspots = data.get('hotspots', [])

        if timestamp_str:
            try:
                ts = datetime.fromisoformat(timestamp_str)
                if timezone.is_naive(ts):
                    ts = timezone.make_aware(ts)
            except (ValueError, TypeError):
                ts = timezone.now()
        else:
            ts = timezone.now()

        # 存储图像记录（上传到 OSS + 本地备份）
        from .oss_utils import (
            upload_bytes_to_oss, generate_oss_key, save_image_locally,
        )
        import base64 as b64

        oss_image_key = ''
        oss_annotated_key = ''

        # 处理原始红外图像
        if image_b64:
            try:
                image_bytes = b64.b64decode(image_b64)
                oss_key = generate_oss_key(device_id, ts, suffix='.jpg')
                result = upload_bytes_to_oss(image_bytes, oss_key)
                if result:
                    oss_image_key = result
                # 本地备份
                local_ts = timezone.localtime(ts)
                date_str = local_ts.strftime('%Y-%m-%d')
                time_str = local_ts.strftime('%Y%m%d_%H%M%S')
                local_rel_path = f'alarm_images/{device_id}/{date_str}/{time_str}_{device_id}.jpg'
                save_image_locally(image_bytes, local_rel_path)
            except Exception as e:
                logger.error(f'处理原始红外图像失败: {e}')

        # 处理标注图像
        if annotated_b64:
            try:
                annotated_bytes = b64.b64decode(annotated_b64)
                oss_ann_key = generate_oss_key(device_id, ts, suffix='_annotated.jpg')
                result = upload_bytes_to_oss(annotated_bytes, oss_ann_key)
                if result:
                    oss_annotated_key = result
            except Exception as e:
                logger.error(f'处理标注图像失败: {e}')

        ThermalImage.objects.create(
            timestamp=ts,
            device_id=device_id,
            image_path=oss_image_key,
            annotated_path=oss_annotated_key,
            width=width,
            height=height,
            hotspots=hotspots,
        )

        # 通过 SSE 广播图像帧
        image_event = {
            'timestamp': timezone.localtime(ts).isoformat(),
            'image': f'data:image/jpeg;base64,{image_b64}',
            'annotated': f'data:image/jpeg;base64,{annotated_b64}',
            'width': width,
            'height': height,
        }
        sse_manager.broadcast('image', json.dumps(image_event, ensure_ascii=False))

    @staticmethod
    def handle_device_offline(device_id: str):
        """
        处理设备离线
        """
        # 标记树莓派离线
        DeviceStatus.objects.filter(
            device_type='raspberrypi',
            device_id=device_id,
        ).update(status='offline')

        # 标记所有支路为离线告警状态
        BranchStatus.objects.all().update(alarm_status='alarm')

        # 触发离线告警
        now = timezone.now()
        for bid in range(1, 5):
            AlarmRecord.objects.create(
                branch=bid,
                alarm_type='offline',
                temperature=None,
                area_ratio=None,
                status='pending',
                description=f'{bid}号支路设备离线，无法获取数据',
                timestamp=now,
            )

        # SSE 广播设备离线状态
        status_data = DashboardService.get_realtime_status()
        sse_manager.broadcast('status', json.dumps(status_data, ensure_ascii=False))
