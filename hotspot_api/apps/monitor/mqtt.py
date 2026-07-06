"""
MQTT 客户端模块
--------------
负责与 MQTT Broker 通信：
- 订阅上行主题: pv/hotspot/up/status（温度/状态）、pv/hotspot/up/image（红外图像）
- 发布下行主题: pv/hotspot/down/control（控制指令）
"""
import json
import logging
import threading
import time

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('monitor.mqtt')


class MQTTClient:
    """
    MQTT 客户端（单例）
    在后台线程中运行，自动重连
    """

    _instance = None
    _lock = threading.Lock()

    # MQTT 主题定义
    TOPIC_STATUS_UP = 'pv/hotspot/up/status'
    TOPIC_IMAGE_UP = 'pv/hotspot/up/image'
    TOPIC_CONTROL_DOWN = 'pv/hotspot/down/control'

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._client = None
        self._connected = False
        self._running = False
        self._thread = None

        # 从配置读取 Broker 地址（默认值用于开发）
        self._broker_host = 'localhost'
        self._broker_port = 1883
        self._keepalive = 60
        self._load_broker_config()

    def _load_broker_config(self):
        """从数据库加载 MQTT Broker 配置"""
        try:
            from .models import SystemConfig
            host_cfg = SystemConfig.objects.filter(config_key='mqtt_broker_host').first()
            port_cfg = SystemConfig.objects.filter(config_key='mqtt_broker_port').first()
            if host_cfg:
                self._broker_host = host_cfg.config_value
            if port_cfg:
                self._broker_port = int(port_cfg.config_value)
        except Exception as e:
            logger.warning(f'加载 MQTT 配置失败，使用默认值: {e}')

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        """启动 MQTT 客户端（后台线程）"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='mqtt-client')
        self._thread.start()
        logger.info(f'MQTT 客户端已启动，Broker: {self._broker_host}:{self._broker_port}')

    def stop(self):
        """停止 MQTT 客户端"""
        self._running = False
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
        logger.info('MQTT 客户端已停止')

    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def _run_loop(self):
        """后台主循环：连接、订阅、消息处理、自动重连"""
        import paho.mqtt.client as mqtt

        while self._running:
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                client.on_connect = self._on_connect
                client.on_disconnect = self._on_disconnect
                client.on_message = self._on_message

                # 设置遗嘱消息（连接异常断开时通知）
                will_payload = json.dumps({
                    'device_id': 'backend-pc',
                    'status': 'offline',
                    'timestamp': timezone.localtime(timezone.now()).isoformat(),
                })
                client.will_set('pv/hotspot/up/backend_status', will_payload, qos=1)

                client.connect(self._broker_host, self._broker_port, self._keepalive)
                self._client = client

                # 等待连接完成（必须调用 loop() 才能完成 MQTT 握手，
                # _on_connect 回调会设置 self._connected = True）
                wait_start = time.time()
                while self._running and not self._connected and (time.time() - wait_start) < 10:
                    client.loop(timeout=0.2)

                if not self._connected:
                    logger.warning(f'MQTT 连接超时（{self._broker_host}:{self._broker_port}），将重试...')
                    try:
                        client.disconnect()
                    except Exception:
                        pass
                    time.sleep(5)
                    continue

                # 主循环：阻塞直到断开或停止
                while self._running and self._connected:
                    client.loop(timeout=1.0)

            except OSError as e:
                logger.error(f'MQTT 网络错误: {e}，5秒后重连...')
                self._connected = False
            except Exception as e:
                logger.error(f'MQTT 连接异常: {e}，5秒后重连...')
                self._connected = False

            if self._running:
                time.sleep(5)  # 重连间隔

    # ------------------------------------------------------------------
    # 回调
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """连接成功回调"""
        if reason_code == 0:
            self._connected = True
            logger.info(f'MQTT 已连接到 Broker: {self._broker_host}:{self._broker_port}')

            # 订阅上行数据主题
            client.subscribe(self.TOPIC_STATUS_UP, qos=1)
            client.subscribe(self.TOPIC_IMAGE_UP, qos=1)
            logger.info(f'已订阅主题: {self.TOPIC_STATUS_UP}, {self.TOPIC_IMAGE_UP}')

            # 更新设备状态
            self._update_device_status('mqtt', 'connected')
            self._publish_backend_online()
        else:
            self._connected = False
            logger.warning(f'MQTT 连接失败，reason_code={reason_code}')

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        """断开连接回调"""
        self._connected = False
        logger.warning(f'MQTT 断开连接，reason_code={reason_code}')
        self._update_device_status('mqtt', 'offline')

    def _on_message(self, client, userdata, msg):
        """接收消息回调"""
        try:
            payload_str = msg.payload.decode('utf-8')
            data = json.loads(payload_str)
            topic = msg.topic

            from .services import MQTTDataProcessor

            if topic == self.TOPIC_STATUS_UP:
                MQTTDataProcessor.process_status(data)

            elif topic == self.TOPIC_IMAGE_UP:
                MQTTDataProcessor.process_image(data)

            else:
                logger.debug(f'收到未知主题消息: {topic}')

        except json.JSONDecodeError:
            logger.error(f'MQTT 消息 JSON 解析失败: {msg.payload[:200]}')
        except Exception as e:
            logger.error(f'MQTT 消息处理异常: {e}', exc_info=True)

    # ------------------------------------------------------------------
    # 发布
    # ------------------------------------------------------------------

    def publish_control(self, payload: dict):
        """
        发布控制指令到下行主题

        参数:
            payload: 控制指令字典，如 {"command": "reset", "branch": 2, ...}
        """
        if not self._connected or self._client is None:
            raise ConnectionError('MQTT 未连接，无法发送控制指令')

        try:
            msg_info = self._client.publish(
                self.TOPIC_CONTROL_DOWN,
                json.dumps(payload, ensure_ascii=False),
                qos=1,
            )
            logger.info(f'MQTT 控制指令已发送: {payload.get("command")} 支路{payload.get("branch")}')
            return msg_info
        except Exception as e:
            logger.error(f'MQTT 发布失败: {e}')
            raise ConnectionError(f'MQTT 发布失败: {e}')

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _update_device_status(self, device_type: str, status: str):
        """更新设备在线状态到数据库"""
        try:
            from .models import DeviceStatus
            DeviceStatus.objects.update_or_create(
                device_type=device_type,
                device_id='default',
                defaults={'status': status},
            )
        except Exception as e:
            logger.debug(f'更新设备状态失败: {e}')

    def _publish_backend_online(self):
        """发布后端上线通知"""
        try:
            payload = json.dumps({
                'device_id': 'backend-pc',
                'status': 'online',
                'timestamp': timezone.localtime(timezone.now()).isoformat(),
            })
            self._client.publish('pv/hotspot/up/backend_status', payload, qos=1)
        except Exception:
            pass


# ------------------------------------------------------------------
# 全局单例
# ------------------------------------------------------------------

mqtt_client = MQTTClient()
