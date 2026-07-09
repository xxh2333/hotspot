import sys
import threading
from django.apps import AppConfig


class MonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.monitor'
    verbose_name = '实时监控面板'

    def ready(self):
        """
        Django 启动时自动初始化默认数据和 MQTT 客户端。
        管理命令（migrate 等）跳过；生产/开发服务器自动启动 MQTT。
        可通过环境变量 ENABLE_MQTT=false 关闭。

        使用线程延迟初始化，避免 ASGI (uvicorn) 的 async context 冲突。
        """
        # 跳过管理命令
        if any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'collectstatic', 'shell', 'createsuperuser']):
            return

        import os

        # runserver 的自动重载器会启动两个进程，只在子进程中初始化
        if 'runserver' in sys.argv:
            if os.environ.get('RUN_MAIN') != 'true':
                return

        enable_mqtt = os.environ.get('ENABLE_MQTT', 'true').lower() != 'false'

        # 延迟 1 秒在线程中初始化，让 Django 完全启动后再操作数据库
        threading.Thread(
            target=self._delayed_init,
            args=(enable_mqtt,),
            daemon=True,
            name='monitor-init',
        ).start()

    @staticmethod
    def _delayed_init(enable_mqtt: bool):
        """延迟初始化：等 Django 就绪后再写数据库和启动 MQTT"""
        import time
        time.sleep(1)

        MonitorConfig._init_defaults()

        if enable_mqtt:
            MonitorConfig._start_mqtt()

    @staticmethod
    def _init_defaults():
        """初始化默认数据库记录（幂等操作）"""
        try:
            from .models import BranchStatus, SystemConfig, DeviceStatus

            # 初始化4个支路的默认状态
            for i in range(1, 5):
                BranchStatus.objects.get_or_create(
                    branch=i,
                    defaults={
                        'temperature': 0.0,
                        'area_ratio': 0.0,
                        'breaker_status': 'closed',
                        'alarm_status': 'normal',
                    }
                )

            # 初始化默认阈值配置
            SystemConfig.objects.get_or_create(
                config_key='temperature_threshold',
                defaults={'config_value': '80.0', 'description': '温度告警阈值(℃)'}
            )
            SystemConfig.objects.get_or_create(
                config_key='area_ratio_threshold',
                defaults={'config_value': '5.0', 'description': '面积告警阈值(%)'}
            )
            SystemConfig.objects.get_or_create(
                config_key='mqtt_broker_host',
                defaults={'config_value': 'broker.emqx.io', 'description': 'MQTT Broker地址'}
            )
            SystemConfig.objects.get_or_create(
                config_key='mqtt_broker_port',
                defaults={'config_value': '1883', 'description': 'MQTT Broker端口'}
            )

            # 初始化设备状态
            DeviceStatus.objects.get_or_create(
                device_type='thermal_camera',
                device_id='default',
                defaults={'status': 'online', 'extra_info': {'fps': 1.0}}
            )
            DeviceStatus.objects.get_or_create(
                device_type='mqtt',
                device_id='default',
                defaults={'status': 'connected'}
            )
            DeviceStatus.objects.get_or_create(
                device_type='raspberrypi',
                device_id='raspberrypi-01',
                defaults={'status': 'online'}
            )

        except Exception as e:
            import logging
            logging.getLogger('monitor').warning(f'初始化默认数据失败: {e}')

    @staticmethod
    def _start_mqtt():
        """启动 MQTT 客户端后台线程"""
        try:
            from .mqtt import mqtt_client
            mqtt_client.start()
        except Exception as e:
            import logging
            logging.getLogger('monitor').warning(f'MQTT 启动失败: {e}')
