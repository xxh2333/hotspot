"""
光伏热斑智能检测系统 — MQTT 数据模拟器
==========================================
模拟树莓派向 MQTT Broker 发送各支路温度与热斑数据。
数据格式匹配 temperature_records 表结构。

依赖安装：pip install paho-mqtt

启动方式：python mqtt_simulator.py
"""

import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import paho.mqtt.client as mqtt

# 修复 Windows 中文环境下 Unicode 字符打印报错的问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════
BROKER_HOST = "localhost"
BROKER_PORT = 1883
QOS = 1

# 四个支路各自的发布主题
TOPICS = {
    1: "sensor/branch/1",
    2: "sensor/branch/2",
    3: "sensor/branch/3",
    4: "sensor/branch/4",
}

PUBLISH_INTERVAL = 5  # 秒

# 北京时间时区
TZ_SHANGHAI = timezone(timedelta(hours=8))


def now_iso() -> str:
    """
    返回当前北京时间，ISO 8601 格式（含毫秒）。
    示例: "2026-07-03T14:35:12.345"
    """
    return datetime.now(TZ_SHANGHAI).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def generate_payload(branch: int) -> dict:
    """
    为指定支路生成一条模拟数据，字段与 temperature_records 表对齐。
    """
    max_temp = round(random.uniform(30.0, 120.0), 2)
    min_temp = round(random.uniform(20.0, 35.0), 2)
    # 保证 avg_temp 介于 min_temp 与 max_temp 之间
    avg_temp = round(random.uniform(float(min_temp), float(max_temp)), 2)

    area_ratio = round(random.uniform(0.0, 25.0), 2)
    hotspot_count = random.randint(0, 3)

    # 热斑面积 > 5% 时热点数至少为 1
    if area_ratio > 5.0 and hotspot_count == 0:
        hotspot_count = random.randint(1, 3)

    return {
        "branch": branch,
        "timestamp": now_iso(),
        "max_temp": max_temp,
        "min_temp": min_temp,
        "avg_temp": avg_temp,
        "area_ratio": area_ratio,
        "hotspot_count": hotspot_count,
    }


def on_connect(client, userdata, flags, rc, properties=None):
    """MQTT 连接回调"""
    if rc == 0:
        print(f"[OK] 已连接到 MQTT Broker: {BROKER_HOST}:{BROKER_PORT}")
    else:
        print(f"[FAIL] 连接失败，返回码: {rc}")


def on_disconnect(client, userdata, flags, rc, properties=None):
    """MQTT 断开回调"""
    if rc != 0:
        print(f"[!] 意外断开连接 (rc={rc})，尝试自动重连...")


def on_publish(client, userdata, mid, properties=None):
    """发布回调"""
    # 静默回调，避免刷屏；取消注释可调试
    # print(f"  -> 消息 {mid} 已送达")
    pass


def build_client() -> mqtt.Client:
    """创建并配置 MQTT 客户端"""
    client = mqtt.Client(
        client_id=f"simulator_{random.randint(1000, 9999)}",
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    # 自动重连
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    return client


def main():
    print("=" * 64)
    print("  光伏热斑检测系统 — MQTT 数据模拟器")
    print("=" * 64)
    print(f"  Broker:  {BROKER_HOST}:{BROKER_PORT}")
    print(f"  主题:    {', '.join(TOPICS.values())}")
    print(f"  频率:    每 {PUBLISH_INTERVAL} 秒一轮（4 条消息）")
    print(f"  QoS:     {QOS}")
    print("-" * 64)

    client = build_client()

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except ConnectionRefusedError:
        print("[✗] 无法连接 MQTT Broker，请确认 EMQX/Mosquitto 已启动")
        print(f"    安装 Mosquitto: https://mosquitto.org/download/")
        return
    except OSError as e:
        print(f"[✗] 网络错误: {e}")
        return

    client.loop_start()
    round_num = 0

    try:
        while True:
            round_num += 1
            print(f"\n── 第 {round_num} 轮 {datetime.now(TZ_SHANGHAI).strftime('%H:%M:%S')} ──")

            for branch in range(1, 5):
                topic = TOPICS[branch]
                payload = generate_payload(branch)
                payload_json = json.dumps(payload, ensure_ascii=False)

                result = client.publish(topic, payload_json, qos=QOS)

                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(
                        f"  [{topic}] "
                        f"max_temp={payload['max_temp']:6.1f}℃  "
                        f"avg={payload['avg_temp']:5.1f}℃  "
                        f"area_ratio={payload['area_ratio']:5.1f}%  "
                        f"hotspots={payload['hotspot_count']}"
                    )
                else:
                    print(f"  [{topic}] 发送失败! rc={result.rc}")

            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n[·] 收到中断信号，正在停止...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[✓] 模拟器已退出")


if __name__ == "__main__":
    main()
