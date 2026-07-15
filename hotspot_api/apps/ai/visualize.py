"""
训练可视化模块
--------------
生成训练趋势图（loss 曲线、指标曲线、样本预测对比图），
以及模型信息摘要，供千问/豆包评估训练成果。
"""
import os
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np

import matplotlib
matplotlib.use('Agg')  # 非交互后端
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

import torch
from torch.utils.data import DataLoader

# 中文字体配置（尝试多个常见中文字体）
for _font in ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC',
              'PingFang SC', 'DejaVu Sans']:
    try:
        matplotlib.rcParams['font.sans-serif'] = [_font]
        matplotlib.rcParams['axes.unicode_minus'] = False
        break
    except Exception:
        continue


# ============================================================================
# 训练趋势图
# ============================================================================

def plot_training_curves(
    history: Dict[str, List[float]],
    save_dir: str,
    model_info: Optional[Dict] = None,
):
    """
    绘制完整的训练趋势图

    参数:
        history: {
            'train_loss': [...], 'val_loss': [...],
            'train_iou': [...], 'val_iou': [...],
            'train_dice': [...], 'val_dice': [...],
            'train_acc': [...], 'val_acc': [...],
            'train_precision': [...], 'val_precision': [...],
            'train_recall': [...], 'val_recall': [...],
        }
        save_dir: 图片输出目录
        model_info: 模型信息字典
    """
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    epochs = range(1, len(history.get('train_loss', [])) + 1)

    # ----- 图 1: Loss 曲线 -----
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(epochs, history['train_loss'], 'b-', label='Train Loss', linewidth=1.5)
    ax.plot(epochs, history['val_loss'], 'r-', label='Val Loss', linewidth=1.5)
    ax.set_xlabel('Epoch')
    ax.set_ylabel('Loss')
    ax.set_title('Training & Validation Loss')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout()
    fig.savefig(save_path / '01_loss_curves.png', dpi=150)
    plt.close(fig)

    # ----- 图 2: IoU + Dice 曲线 -----
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(epochs, history['train_iou'], 'b-', label='Train IoU', linewidth=1.5)
    ax1.plot(epochs, history['val_iou'], 'r-', label='Val IoU', linewidth=1.5)
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('IoU')
    ax1.set_title('IoU (Intersection over Union)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True))

    ax2.plot(epochs, history['train_dice'], 'b-', label='Train Dice', linewidth=1.5)
    ax2.plot(epochs, history['val_dice'], 'r-', label='Val Dice', linewidth=1.5)
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Dice')
    ax2.set_title('Dice Coefficient')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.tight_layout()
    fig.savefig(save_path / '02_iou_dice_curves.png', dpi=150)
    plt.close(fig)

    # ----- 图 3: Accuracy + Precision + Recall 曲线 -----
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5))

    for ax, metric_name, title in [
        (ax1, 'acc', 'Pixel Accuracy'),
        (ax2, 'precision', 'Precision'),
        (ax3, 'recall', 'Recall'),
    ]:
        ax.plot(epochs, history[f'train_{metric_name}'], 'b-',
                label=f'Train {title}', linewidth=1.5)
        ax.plot(epochs, history[f'val_{metric_name}'], 'r-',
                label=f'Val {title}', linewidth=1.5)
        ax.set_xlabel('Epoch')
        ax.set_ylabel(title)
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.tight_layout()
    fig.savefig(save_path / '03_accuracy_precision_recall.png', dpi=150)
    plt.close(fig)

    # ----- 图 4: 总览（4 合 1）-----
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    plot_configs = [
        (axes[0, 0], ('train_loss', 'val_loss'), 'Loss', 'Loss'),
        (axes[0, 1], ('train_iou', 'val_iou'), 'IoU', 'IoU'),
        (axes[1, 0], ('train_dice', 'val_dice'), 'Dice', 'Dice Coefficient'),
        (axes[1, 1], ('train_acc', 'val_acc'), 'Accuracy', 'Pixel Accuracy'),
    ]

    for ax, (train_key, val_key), title, ylabel in plot_configs:
        ax.plot(epochs, history[train_key], 'b-', label='Train', linewidth=1.5)
        ax.plot(epochs, history[val_key], 'r-', label='Val', linewidth=1.5)
        ax.set_xlabel('Epoch')
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.suptitle('Training Summary', fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.savefig(save_path / '04_summary.png', dpi=150)
    plt.close(fig)

    print(f'训练趋势图已保存到: {save_path.resolve()}')
    print(f'  - 01_loss_curves.png')
    print(f'  - 02_iou_dice_curves.png')
    print(f'  - 03_accuracy_precision_recall.png')
    print(f'  - 04_summary.png')


# ============================================================================
# 样本预测对比图
# ============================================================================

def plot_sample_predictions(
    model: torch.nn.Module,
    dataloader: DataLoader,
    save_dir: str,
    device: str = 'cpu',
    num_samples: int = 6,
):
    """
    生成样本预测对比图：原图 | 真实 mask | 预测 mask
    """
    save_path = Path(save_dir) / '05_sample_predictions.png'

    model.eval()
    images_list = []
    masks_list = []
    preds_list = []

    with torch.no_grad():
        for batch in dataloader:
            images = batch['image'].to(device)
            masks = batch['mask'].to(device)
            preds = model(images)

            images_list.extend(images.cpu())
            masks_list.extend(masks.cpu())
            preds_list.extend(preds.cpu())

            if len(images_list) >= num_samples:
                break

    n = min(num_samples, len(images_list))
    fig, axes = plt.subplots(n, 3, figsize=(9, 3 * n))

    if n == 1:
        axes = axes.reshape(1, -1)

    for i in range(n):
        img = images_list[i].squeeze().numpy()
        mask = masks_list[i].squeeze().numpy()
        pred = (preds_list[i].squeeze().numpy() > 0.5).astype(np.float32)

        # 原图（如果是单通道灰度）
        axes[i, 0].imshow(img, cmap='gray' if img.ndim == 2 else None)
        axes[i, 1].imshow(mask, cmap='gray')
        axes[i, 2].imshow(pred, cmap='gray')

        for j, title in enumerate(['Original', 'Ground Truth', 'Prediction']):
            axes[i, j].set_title(title if i == 0 else '')
            axes[i, j].axis('off')

    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f'样本预测图已保存到: {save_path.resolve()}')


# ============================================================================
# 最佳指标汇总
# ============================================================================

def print_best_metrics(history: Dict[str, List[float]]):
    """打印各指标最佳值"""
    print()
    print('=' * 55)
    print('  Training Complete - Best Metrics')
    print('=' * 55)

    metrics_display = [
        ('val_loss', 'Loss', 'min'),
        ('val_iou', 'IoU', 'max'),
        ('val_dice', 'Dice', 'max'),
        ('val_acc', 'Pixel Accuracy', 'max'),
        ('val_precision', 'Precision', 'max'),
        ('val_recall', 'Recall', 'max'),
    ]

    best_dict = {}
    for key, label, direction in metrics_display:
        if key not in history or not history[key]:
            continue
        values = history[key]
        if direction == 'min':
            best_val = min(values)
            best_epoch = values.index(best_val) + 1
        else:
            best_val = max(values)
            best_epoch = values.index(best_val) + 1
        print(f'  {label:<20s}: {best_val:.4f}  (epoch {best_epoch})')
        best_dict[f'best_{key}'] = best_val
        best_dict[f'best_{key}_epoch'] = best_epoch

    print('=' * 55)
    return best_dict
