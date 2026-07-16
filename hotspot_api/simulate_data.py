#!/usr/bin/env python
"""
模拟树莓派数据采集脚本
-----------------------
用于在没有实际硬件的环境下模拟 SSE 实时数据流动。

每 5 秒发送温度/状态数据 → 主题: pv/hotspot/up/status
每 1 秒发送红外热像图     → 主题: pv/hotspot/up/image

使用方式：
    1. 确保后端 MQTT 客户端已启动（ENABLE_MQTT=true 或不设该变量）
    2. python simulate_data.py
"""
import json
import time
import random
import base64
import struct
import os
import sys

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paho.mqtt.client as mqtt
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# MQTT Broker 配置（与团队 settings.py 一致）
# ---------------------------------------------------------------------------
BROKER_HOST = 'broker.emqx.io'
BROKER_PORT = 1883
DEVICE_ID = 'raspberrypi-01'

# 主题（与 monitor/mqtt.py 一致）
TOPIC_STATUS = 'pv/hotspot/up/status'
TOPIC_IMAGE = 'pv/hotspot/up/image'

# 4 路支路配置
BRANCHES = [1, 2, 3, 4]

# 模拟温度基线（℃），每条支路有不同的正常温度范围
BASE_TEMP = {1: 40.0, 2: 42.0, 3: 38.0, 4: 41.0}


# ---------------------------------------------------------------------------
# 红外热像图生成（简易模拟）
# ---------------------------------------------------------------------------

def generate_thermal_image(hotspot_branch=None, hotspot_temp=0.0):
    """
    生成一张模拟的红外热像图 (Base64 JPEG)。

    实际项目中树莓派连接红外相机采集真实图像，
    这里用简单的 PPM → 伪 JPEG 来模拟数据流动。
    """
    width, height = 256, 192
    pixels = []

    for y in range(height):
        for x in range(width):
            # 背景温度：32~38℃ 随机波动
            temp = 32.0 + random.uniform(0, 6.0)

            # 如果在热斑支路上，在图像中心区域叠加高温
            if hotspot_branch and hotspot_temp > 60:
                cx, cy = 128 + (hotspot_branch - 2.5) * 40, 96
                dx, dy = x - cx, y - cy
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < 50:
                    temp = max(temp, hotspot_temp - dist * 0.5)

            # 温度 → RGB（蓝=低温，绿=中温，红=高温）
            r, g, b = temp_to_rgb(temp)
            pixels.append((r, g, b))

    # 生成 PPM 格式的二进制数据
    ppm_header = f'P6\n{width} {height}\n255\n'.encode()
    ppm_data = b''.join(struct.pack('BBB', *c) for c in pixels)

    return base64.b64encode(ppm_header + ppm_data).decode()


def temp_to_rgb(temp):
    """温度值映射到红外伪彩色（蓝→青→绿→黄→红）"""
    t = (temp - 25) / 80  # 归一化 25~105℃ → 0~1
    t = max(0.0, min(1.0, t))

    if t < 0.25:
        # 蓝 → 青
        r, g, b = 0, int(t / 0.25 * 255), 255
    elif t < 0.5:
        # 青 → 绿
        r, g, b = 0, 255, int((1 - (t - 0.25) / 0.25) * 255)
    elif t < 0.75:
        # 绿 → 黄
        r, g, b = int((t - 0.5) / 0.25 * 255), 255, 0
    else:
        # 黄 → 红
        r, g, b = 255, int((1 - (t - 0.75) / 0.25) * 255), 0

    return (r, g, b)


# ---------------------------------------------------------------------------
# 数据生成
# ---------------------------------------------------------------------------

def generate_status_data():
    """生成模拟的温度/状态数据"""
    now = datetime.now(timezone(timedelta(hours=8)))
    branches = []
    breaker_status = {}

    for bid in BRANCHES:
        # 正常波动 ±3℃，偶尔出现高温
        if random.random() < 0.15:  # 15% 概率出现温度异常
            temperature = BASE_TEMP[bid] + random.uniform(30, 50)
            area_ratio = round(random.uniform(4.0, 12.0), 1)
        else:
            temperature = BASE_TEMP[bid] + random.uniform(-3, 3)
            area_ratio = 0.0

        branches.append({
            'id': bid,
            'temperature': round(temperature, 1),
            'area_ratio': area_ratio,
        })
        breaker_status[str(bid)] = 'closed'

    return {
        'timestamp': now.isoformat(),
        'device_id': DEVICE_ID,
        'branches': branches,
        'breaker_status': breaker_status,
        'thermal_camera': 'online',
    }


def generate_image_data(status_payload):
    """根据当前温度数据生成模拟的红外热像图"""
    now = datetime.now(timezone(timedelta(hours=8)))
    branches = status_payload['branches']

    # 找最高温度支路作为热斑位置
    max_branch = max(branches, key=lambda b: b['temperature'])
    hotspot_temp = max_branch['temperature']

    raw_image = generate_thermal_image(
        hotspot_branch=max_branch['id'] if hotspot_temp > 60 else None,
        hotspot_temp=hotspot_temp,
    )
    annotated_image = raw_image  # 模拟标注图与原图一致

    hotspots = []
    if hotspot_temp > 60:
        hotspots = [{
            'x': int(128 + (max_branch['id'] - 2.5) * 40),
            'y': 96,
            'width': 40,
            'height': 35,
            'temp': hotspot_temp,
        }]

    return {
        'timestamp': now.isoformat(),
        'device_id': DEVICE_ID,
        'image': raw_image,
        'annotated_image': annotated_image,
        'width': 256,
        'height': 192,
        'hotspots': hotspots,
    }


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def main():
    print(f'[*] 连接 MQTT Broker: {BROKER_HOST}:{BROKER_PORT}')
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()

    print(f'[*] 开始模拟数据发送，设备: {DEVICE_ID}')
    print(f'    - 温度/状态: 每 5 秒 → {TOPIC_STATUS}')
    print(f'    - 红外图像:   每 1 秒 → {TOPIC_IMAGE}')
    print(f'    - 约 15% 概率产生温度异常数据')
    print()
    print(f'    按 Ctrl+C 停止')
    print('=' * 60)

    last_status_time = 0
    last_image_time = 0
    status_payload = None
    count_status = 0
    count_image = 0

    try:
        while True:
            now_ts = time.time()

            # 每 5 秒发送温度/状态
            if now_ts - last_status_time >= 5:
                status_payload = generate_status_data()
                client.publish(
                    TOPIC_STATUS,
                    json.dumps(status_payload, ensure_ascii=False),
                    qos=1,
                )
                count_status += 1

                # 打印当前温度
                parts = []
                for b in status_payload['branches']:
                    s = '支路{}:{}℃'.format(b['id'], b['temperature'])
                    if b['area_ratio'] > 0:
                        s += ' 🔥热斑{}%'.format(b['area_ratio'])
                    parts.append(s)
                print('[状态 #{}] {}'.format(count_status, ', '.join(parts)))
                last_status_time = now_ts

            # 每 5 分钟发送红外图像
            if now_ts - last_image_time >= 300:
                if status_payload:
                    image_payload = generate_image_data(status_payload)
                else:
                    temp = {'id': 1, 'temperature': 40}
                    image_payload = generate_image_data({
                        'branches': [temp]
                    })

                client.publish(
                    TOPIC_IMAGE,
                    json.dumps(image_payload, ensure_ascii=False),
                    qos=1,
                )
                count_image += 1
                hotspots = image_payload.get('hotspots', [])
                marker = ' 🔴检测到热斑' if hotspots else ''
                print(f'[图像 #{count_image}] 256x192, {len(image_payload["image"])} bytes base64{marker}')
                last_image_time = now_ts

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print('=' * 60)
        print(f'[!] 已停止。共发送 {count_status} 条状态 + {count_image} 条图像')
        client.loop_stop()
        client.disconnect()


if __name__ == '__main__':
    main()
