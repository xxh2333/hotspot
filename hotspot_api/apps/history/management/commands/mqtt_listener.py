"""
Django 自定义管理命令 — MQTT 数据监听器
=========================================
后台常驻运行，订阅 sensor/branch/# 主题，
将树莓派上报的温度数据实时写入 monitor_temperature_record 表。

启动方式：
    python manage.py mqtt_listener

停止方式：
    Ctrl+C（优雅退出）
"""

import json
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta

import paho.mqtt.client as mqtt
from django.core.management.base import BaseCommand
from django.db import DatabaseError, IntegrityError
from django.utils import timezone as django_timezone

from apps.history.models import TemperatureRecord

logger = logging.getLogger(__name__)

# ── 常量 ──
TZ_SHANGHAI = timezone(timedelta(hours=8))

# TemperatureRecord 字段列表（用于校验）
REQUIRED_FIELDS = {'branch', 'timestamp', 'max_temp', 'avg_temp', 'area_ratio'}

# 数据合理性边界
BRANCH_RANGE = (1, 4)
TEMP_RANGE = (-20.0, 150.0)
AREA_RATIO_RANGE = (0.0, 100.0)


def parse_timestamp(ts_str: str) -> datetime | None:
    """
    解析 ISO 8601 时间字符串（兼容多种格式），返回 naive datetime。

    支持格式：
      - "2026-07-03T14:35:12.345"
      - "2026-07-03T14:35:12"
      - "2026-07-03 14:35:12.345"
    """
    if not ts_str:
        return None
    for fmt in (
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
    ):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def validate_payload(data: dict) -> list[str]:
    """
    校验一条 MQTT 消息的字段完整性和合理性。
    返回错误信息列表，空列表表示校验通过。
    """
    errors = []

    # 1. 字段完整性
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"缺少必填字段: {missing}")
        # 缺少关键字段直接返回，避免后续校验报错
        return errors

    # 2. branch
    branch = data['branch']
    if not isinstance(branch, int) or not (BRANCH_RANGE[0] <= branch <= BRANCH_RANGE[1]):
        errors.append(f"branch 超出范围: {branch}（期望 {BRANCH_RANGE[0]}~{BRANCH_RANGE[1]}）")

    # 3. timestamp
    ts = parse_timestamp(data['timestamp'])
    if ts is None:
        errors.append(f"无法解析 timestamp: {data['timestamp']}")

    # 4. 温度字段
    for field in ('max_temp', 'avg_temp'):
        val = data.get(field)
        if not isinstance(val, (int, float)):
            errors.append(f"{field} 不是数值类型: {val}")
        elif not (TEMP_RANGE[0] <= val <= TEMP_RANGE[1]):
            errors.append(f"{field} 超出合理范围: {val}（期望 {TEMP_RANGE[0]}~{TEMP_RANGE[1]}）")

    # 5. area_ratio
    ar = data['area_ratio']
    if not isinstance(ar, (int, float)) or not (AREA_RATIO_RANGE[0] <= ar <= AREA_RATIO_RANGE[1]):
        errors.append(f"area_ratio 超出范围: {ar}（期望 {AREA_RATIO_RANGE[0]}~{AREA_RATIO_RANGE[1]}）")

    return errors


class Command(BaseCommand):
    """
    MQTT 数据监听命令

    订阅 sensor/branch/# 主题，将收到的温度数据写入 temperature_records 表。
    常驻进程，按 Ctrl+C 优雅退出。
    """

    help = '启动 MQTT 监听器，订阅 sensor/branch/# 并持续写入 monitor_temperature_record 表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--host', type=str, default='localhost',
            help='MQTT Broker 地址（默认 localhost）',
        )
        parser.add_argument(
            '--port', type=int, default=1883,
            help='MQTT Broker 端口（默认 1883）',
        )
        parser.add_argument(
            '--topic', type=str, default='sensor/branch/#',
            help='订阅主题（默认 sensor/branch/#）',
        )
        parser.add_argument(
            '--qos', type=int, default=1,
            help='QoS 等级（默认 1）',
        )

    # ── MQTT 回调 ─────────────────────────────

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self.stdout.write(self.style.SUCCESS(
                f'[MQTT] 已连接 → {userdata["host"]}:{userdata["port"]}'
            ))
            client.subscribe(userdata['topic'], qos=userdata['qos'])
            self.stdout.write(f'[MQTT] 已订阅 → {userdata["topic"]}')
        else:
            self.stderr.write(f'[MQTT] 连接失败，返回码: {reason_code}')

    def on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            self.stderr.write(f'[MQTT] 意外断开 (rc={reason_code})，自动重连中...')

    def on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        topic = msg.topic
        userdata['msg_count'] += 1  # type: ignore
        count = userdata['msg_count']

        # ── 1. 解码 ──
        try:
            payload_str = msg.payload.decode('utf-8')
        except UnicodeDecodeError as e:
            self.stderr.write(f'[#{count}] {topic} → 解码失败: {e}')
            return

        # ── 2. 解析 JSON ──
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError as e:
            self.stderr.write(f'[#{count}] {topic} → JSON 解析失败: {e}')
            return

        self.stdout.write(
            f'[#{count}] {topic} → '
            f'branch={data.get("branch")}, '
            f'max_temp={data.get("max_temp")}, '
            f'area_ratio={data.get("area_ratio")}'
        )

        # ── 3. 校验 ──
        errors = validate_payload(data)
        if errors:
            for err in errors:
                self.stderr.write(f'[#{count}] {topic} → 校验失败: {err}')
            return

        # ── 4. 写入数据库 ──
        try:
            ts = parse_timestamp(data['timestamp'])
            if ts is None:
                self.stderr.write(f'[#{count}] {topic} → 时间戳解析失败，跳过')
                return

            # 使用 update_or_create 避免时间戳+支路重复（幂等写入）
            record, created = TemperatureRecord.objects.update_or_create(
                branch=data['branch'],
                timestamp=ts,
                defaults={
                    'max_temp': data['max_temp'],
                    'avg_temp': data['avg_temp'],
                    'area_ratio': data['area_ratio'],
                },
            )

            action = 'INSERT' if created else 'UPDATE'
            self.stdout.write(
                f'  → {action} id={record.id} '
                f'branch={record.branch} '
                f'timestamp={record.timestamp}'
            )

        except IntegrityError as e:
            self.stderr.write(f'[#{count}] {topic} → 数据库完整性错误: {e}')
        except DatabaseError as e:
            self.stderr.write(f'[#{count}] {topic} → 数据库异常: {e}')
        except Exception as e:
            self.stderr.write(f'[#{count}] {topic} → 未知异常: {type(e).__name__}: {e}')

    # ── 主入口 ────────────────────────────────

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        topic = options['topic']
        qos = options['qos']

        self.stdout.write(self.style.SUCCESS('=' * 56))
        self.stdout.write(self.style.SUCCESS('  MQTT 数据监听器'))
        self.stdout.write(self.style.SUCCESS('=' * 56))
        self.stdout.write(f'  Broker:  {host}:{port}')
        self.stdout.write(f'  主题:    {topic}')
        self.stdout.write(f'  QoS:     {qos}')
        self.stdout.write(f'  目标表:  temperature_records')
        self.stdout.write('-' * 56)
        self.stdout.write('  按 Ctrl+C 停止监听\n')

        # 用户数据字典，回调中通过 userdata 共享
        userdata = {
            'host': host,
            'port': port,
            'topic': topic,
            'qos': qos,
            'msg_count': 0,
        }

        client = mqtt.Client(
            client_id=f'django_listener_{host}',
            protocol=mqtt.MQTTv5,
            userdata=userdata,
        )
        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        client.on_message = self.on_message
        client.reconnect_delay_set(min_delay=1, max_delay=30)

        # ── 信号处理（优雅退出） ──
        shutdown_flag = {'shutdown': False}

        def signal_handler(signum, frame):
            self.stdout.write('\n[·] 收到中断信号，正在停止...')
            shutdown_flag['shutdown'] = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # ── 连接 ──
        try:
            client.connect(host, port, keepalive=60)
        except ConnectionRefusedError:
            self.stderr.write(self.style.ERROR(
                f'无法连接 MQTT Broker ({host}:{port})，请确认 Broker 已启动'
            ))
            sys.exit(1)
        except OSError as e:
            self.stderr.write(self.style.ERROR(f'网络错误: {e}'))
            sys.exit(1)

        client.loop_start()

        # ── 主循环 ──
        try:
            while not shutdown_flag['shutdown']:
                # sleep 分段，以便及时响应中断信号
                for _ in range(10):
                    if shutdown_flag['shutdown']:
                        break
                    import time
                    time.sleep(0.1)
        finally:
            client.loop_stop()
            client.disconnect()
            self.stdout.write(self.style.SUCCESS(
                f'[✓] 监听器已退出（共处理 {userdata["msg_count"]} 条消息）'
            ))
