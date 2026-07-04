import sys
from django.apps import AppConfig


class MonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.monitor'
    verbose_name = '实时监控面板'

    def ready(self):
        """
        Django 启动时自动初始化默认数据和 MQTT 客户端
        仅在 runserver 主进程中执行，避免在 migrate/makemigrations 等命令中触发
        """
        # 跳过管理命令（migrate, makemigrations, collectstatic 等）
        if any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'collectstatic', 'shell', 'createsuperuser']):
            return

        # 仅当通过 runserver 启动时自动初始化
        if 'runserver' in sys.argv:
            import os
            # Django runserver 使用自动重载器，会启动两个进程
            # RUN_MAIN='true' 表示这是实际处理请求的子进程
            if os.environ.get('RUN_MAIN') == 'true':
                self._init_defaults()
                self._start_mqtt()

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
                defaults={'config_value': 'localhost', 'description': 'MQTT Broker地址'}
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
            logging.getLogger('monitor').warning(f'初始化默认数据失败（可能数据库尚未迁移）: {e}')

    @staticmethod
    def _start_mqtt():
        """启动 MQTT 客户端后台线程"""
        try:
            from .mqtt import mqtt_client
            mqtt_client.start()
        except Exception as e:
            import logging
            logging.getLogger('monitor').warning(f'MQTT 启动失败: {e}')
