import json
import threading
import time
from paho.mqtt import client as mqtt_client
from django.conf import settings


class MQTTClient:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.host = settings.MQTT_CONFIG['HOST']
        self.port = settings.MQTT_CONFIG['PORT']
        self.client_id = settings.MQTT_CONFIG['CLIENT_ID']
        self.username = settings.MQTT_CONFIG['USERNAME']
        self.password = settings.MQTT_CONFIG['PASSWORD']
        self.keepalive = settings.MQTT_CONFIG['KEEPALIVE']
        self.topics = settings.MQTT_CONFIG['TOPICS']
        
        self.client = None
        self._connected = False
        self._message_callback = None
        self._initialized = True
    
    def connect(self):
        self.client = mqtt_client.Client(client_id=self.client_id, clean_session=settings.MQTT_CONFIG['CLEAN_SESSION'])
        
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        try:
            self.client.connect(self.host, self.port, self.keepalive)
            self.client.loop_start()
            time.sleep(1)
            return self._connected
        except Exception as e:
            print(f"MQTT连接失败: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            print("MQTT连接成功")
            for topic in self.topics.values():
                self.client.subscribe(topic, qos=1)
                print(f"已订阅主题: {topic}")
        else:
            print(f"MQTT连接失败，返回码: {rc}")
            self._connected = False
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            print(f"收到消息: {msg.topic} -> {payload}")
            
            if self._message_callback:
                self._message_callback(msg.topic, payload)
        except json.JSONDecodeError:
            print(f"消息解析失败: {msg.payload}")
        except Exception as e:
            print(f"消息处理异常: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        print(f"MQTT断开连接，返回码: {rc}")
        if rc != 0:
            print("尝试重连...")
            time.sleep(5)
            self.connect()
    
    def publish(self, topic, data, qos=1):
        if not self._connected:
            print("MQTT未连接，尝试重连")
            if not self.connect():
                return False
        
        try:
            payload = json.dumps(data, ensure_ascii=False)
            result = self.client.publish(topic, payload, qos=qos)
            result.wait_for_publish()
            return result.is_published()
        except Exception as e:
            print(f"MQTT发布失败: {e}")
            return False
    
    def subscribe(self, topic, callback=None):
        if not self._connected:
            if not self.connect():
                return False
        
        self.client.subscribe(topic, qos=1)
        if callback:
            self._message_callback = callback
        return True
    
    def set_message_callback(self, callback):
        self._message_callback = callback
    
    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self._connected = False
            print("MQTT已断开连接")
    
    def is_connected(self):
        return self._connected


mqtt_instance = MQTTClient()