#!/usr/bin/env python
"""
合成数据集生成器
----------------
基于 simulate_data.py 的红外图生成逻辑，批量生成带标注 mask 的模拟数据集。
用于在没有真实标注数据时快速跑通训练流程。

每张图：红外伪彩色图 (PNG) + 二值 mask (PNG，白色=热斑区域)

使用方式：
    python generate_synthetic.py                        # 默认 300 张
    python generate_synthetic.py --samples 1000         # 生成 1000 张
    python generate_synthetic.py --samples 500 --no-hotspot-ratio 0.3  # 30% 无热斑
"""
import argparse
import io
import os
import random
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image


# ============================================================================
# 参数配置
# ============================================================================

DEFAULT_SAMPLES = 300  # 默认总样本数
TRAIN_RATIO = 0.8      # 80% 训练
VAL_RATIO = 0.1        # 10% 验证
# 其余 10% 测试

IMAGE_WIDTH = 256
IMAGE_HEIGHT = 192

# 温度模拟参数
TEMP_BACKGROUND_MIN = 28.0   # 背景最低温度
TEMP_BACKGROUND_MAX = 42.0   # 背景最高温度
TEMP_HOTSPOT_MIN = 55.0      # 热斑最低温度
TEMP_HOTSPOT_MAX = 105.0     # 热斑最高温度

# 热斑形状参数
HOTSPOT_MIN_RADIUS = 10      # 最小半径（像素）
HOTSPOT_MAX_RADIUS = 40      # 最大半径（像素）
HOTSPOTS_PER_IMAGE_MIN = 0
HOTSPOTS_PER_IMAGE_MAX = 3


# ============================================================================
# 伪彩色映射
# ============================================================================

def temp_to_rgb(temp: float) -> tuple:
    """
    温度值 → 红外伪彩色（蓝→青→绿→黄→红）
    与 simulate_data.py 中的映射逻辑保持一致
    """
    t = (temp - 25) / 80  # 归一化到 0~1
    t = max(0.0, min(1.0, t))

    if t < 0.25:
        r, g, b = 0, int(t / 0.25 * 255), 255
    elif t < 0.5:
        r, g, b = 0, 255, int((1 - (t - 0.25) / 0.25) * 255)
    elif t < 0.75:
        r, g, b = int((t - 0.5) / 0.25 * 255), 255, 0
    else:
        r, g, b = 255, int((1 - (t - 0.75) / 0.25) * 255), 0

    return (r, g, b)


# ============================================================================
# 图像生成
# ============================================================================

def generate_background_temperature(height: int, width: int) -> np.ndarray:
    """
    生成背景温度场（2D numpy 数组）
    模拟光伏板不均匀的温度分布——添加低频变化
    """
    # 基础均匀温度
    base_temp = random.uniform(TEMP_BACKGROUND_MIN, TEMP_BACKGROUND_MAX)

    # 添加低频噪声模拟温度不均匀（使用大尺度正弦波叠加）
    xx, yy = np.meshgrid(
        np.linspace(0, 4 * np.pi, width),
        np.linspace(0, 3 * np.pi, height),
    )

    noise = (
        np.sin(xx * 0.7 + random.random() * 2) * 2.0 +
        np.cos(yy * 0.5 + random.random() * 2) * 1.5 +
        np.sin((xx + yy) * 0.3) * 1.0
    )

    return np.full((height, width), base_temp, dtype=np.float32) + noise.astype(np.float32)


def add_hotspot(
    temp_field: np.ndarray,
    cx: int, cy: int, radius: int,
    peak_temp: float,
) -> np.ndarray:
    """
    在温度场上叠加一个热斑（圆形高斯衰减）
    同时返回该热斑的二值 mask
    """
    height, width = temp_field.shape
    yy, xx = np.ogrid[:height, :width]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    # 高斯衰减：中心温度最高，边缘降到背景水平
    sigma = radius / 2.5
    gaussian = np.exp(-0.5 * (dist / sigma) ** 2)
    gaussian[dist > radius * 1.2] = 0  # 截断远处影响

    temp_rise = (peak_temp - TEMP_BACKGROUND_MIN) * gaussian
    temp_field += temp_rise

    # mask：半径内的像素标记为热斑
    mask = (dist <= radius).astype(np.uint8) * 255

    return mask


def generate_single_sample() -> tuple:
    """
    生成一张合成红外图及其热斑标注 mask

    返回: (rgb_image: PIL.Image, mask: PIL.Image, hotspot_count: int)
    """
    height, width = IMAGE_HEIGHT, IMAGE_WIDTH

    # 1. 生成背景温度场
    temp_field = generate_background_temperature(height, width)

    # 2. 随机生成热斑
    num_hotspots = random.randint(HOTSPOTS_PER_IMAGE_MIN, HOTSPOTS_PER_IMAGE_MAX)
    full_mask = np.zeros((height, width), dtype=np.uint8)

    for _ in range(num_hotspots):
        # 随机位置（避免太靠近边缘）
        margin = HOTSPOT_MAX_RADIUS + 5
        cx = random.randint(margin, width - margin)
        cy = random.randint(margin, height - margin)
        radius = random.randint(HOTSPOT_MIN_RADIUS, HOTSPOT_MAX_RADIUS)
        peak_temp = random.uniform(TEMP_HOTSPOT_MIN, TEMP_HOTSPOT_MAX)

        # 在温度场上叠加热斑
        spot_mask = add_hotspot(temp_field, cx, cy, radius, peak_temp)
        full_mask = np.maximum(full_mask, spot_mask)

    # 3. 温度场 → RGB 伪彩色图
    rgb_pixels = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            r, g, b = temp_to_rgb(temp_field[y, x])
            rgb_pixels[y, x] = [r, g, b]

    rgb_image = Image.fromarray(rgb_pixels, mode='RGB')
    mask_image = Image.fromarray(full_mask, mode='L')  # 灰度 mask

    return rgb_image, mask_image, num_hotspots


# ============================================================================
# 批量生成
# ============================================================================

def generate_dataset(output_dir: str, num_samples: int):
    """
    生成完整的 train/val/test 数据集

    目录结构:
        output_dir/
        ├── train/
        │   ├── images/   (PNG 伪彩色图)
        │   └── masks/    (PNG 二值 mask)
        ├── val/
        │   ├── images/
        │   └── masks/
        └── test/
            ├── images/
            └── masks/
    """
    output_path = Path(output_dir)
    train_count = int(num_samples * TRAIN_RATIO)
    val_count = int(num_samples * VAL_RATIO)
    test_count = num_samples - train_count - val_count

    splits = {
        'train': train_count,
        'val': val_count,
        'test': test_count,
    }

    total_hotspots = 0
    total_no_hotspot = 0

    for split_name, count in splits.items():
        img_dir = output_path / split_name / 'images'
        mask_dir = output_path / split_name / 'masks'
        img_dir.mkdir(parents=True, exist_ok=True)
        mask_dir.mkdir(parents=True, exist_ok=True)

        print(f'生成 {split_name} 集: {count} 张...')

        for i in range(count):
            rgb_img, mask_img, num_hs = generate_single_sample()

            # 文件名: split_00001.png
            filename = f'{split_name}_{i:05d}.png'

            rgb_img.save(img_dir / filename)
            mask_img.save(mask_dir / filename)

            total_hotspots += num_hs
            if num_hs == 0:
                total_no_hotspot += 1

            if (i + 1) % 50 == 0:
                print(f'  {split_name}: {i + 1}/{count} 完成')

    # 统计
    print()
    print('=' * 55)
    print(f'  数据集生成完成！')
    print(f'  总计: {num_samples} 张')
    print(f'  训练: {train_count} | 验证: {val_count} | 测试: {test_count}')
    print(f'  热斑总数: {total_hotspots}')
    print(f'  无热斑图: {total_no_hotspot} 张 ({100 * total_no_hotspot / num_samples:.1f}%)')
    print(f'  输出目录: {output_path.resolve()}')
    print('=' * 55)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='生成光伏红外热斑合成数据集',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python generate_synthetic.py                         # 默认 300 张
  python generate_synthetic.py --samples 1000          # 1000 张
  python generate_synthetic.py --samples 500 --seed 42 # 固定随机种子
  python generate_synthetic.py --output ./my_data      # 自定义输出目录
        ''',
    )
    parser.add_argument(
        '--samples', type=int, default=DEFAULT_SAMPLES,
        help=f'总样本数 (默认: {DEFAULT_SAMPLES})',
    )
    parser.add_argument(
        '--output', type=str, default=None,
        help='输出目录 (默认: apps/ai/data)',
    )
    parser.add_argument(
        '--seed', type=int, default=42,
        help='随机种子 (默认: 42)',
    )
    args = parser.parse_args()

    # 设置随机种子
    random.seed(args.seed)
    np.random.seed(args.seed)

    # 输出目录默认在 ai app 同级的 data 目录
    if args.output is None:
        output_dir = Path(__file__).resolve().parent / 'data'
    else:
        output_dir = Path(args.output)

    print(f'开始生成合成数据集...')
    print(f'  样本数: {args.samples}')
    print(f'  图像尺寸: {IMAGE_WIDTH}×{IMAGE_HEIGHT}')
    print(f'  随机种子: {args.seed}')
    print()

    generate_dataset(str(output_dir), args.samples)


if __name__ == '__main__':
    main()
