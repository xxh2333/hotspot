#!/usr/bin/env python
"""
UNet 热斑分割模型训练脚本
-------------------------
训练流程：
  1. 加载数据集
  2. 创建 UNet 模型
  3. 训练循环 (BCE + Dice Loss)
  4. 多指标评估 (IoU, Dice, Accuracy, Precision, Recall)
  5. 保存最佳模型 (model.pth)
  6. 导出 ONNX 格式 (model.onnx)
  7. 生成训练趋势图 → training_plots/

使用方式：
  python train.py                         # 使用默认 config
  python train.py --epochs 50 --lr 5e-5   # 自定义参数
  python train.py --device cuda           # 使用 GPU
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau

# 将 ai 目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import train_config, TrainConfig, AI_APP_DIR
from model import create_model, count_parameters, UNet
from dataset import create_dataloaders
from visualize import (
    plot_training_curves,
    plot_sample_predictions,
    print_best_metrics,
)


# ============================================================================
# 损失函数
# ============================================================================

class DiceLoss(nn.Module):
    """Dice Loss = 1 - (2 * |X∩Y|) / (|X| + |Y|)"""

    def __init__(self, smooth: float = 1e-6):
        super().__init__()
        self.smooth = smooth

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        pred_flat = pred.view(-1)
        target_flat = target.view(-1)
        intersection = (pred_flat * target_flat).sum()
        dice = (2. * intersection + self.smooth) / (
            pred_flat.sum() + target_flat.sum() + self.smooth
        )
        return 1. - dice


class CombinedLoss(nn.Module):
    """BCE + Dice 组合损失"""

    def __init__(self, bce_weight: float = 0.5, dice_weight: float = 0.5):
        super().__init__()
        self.bce = nn.BCELoss()
        self.dice = DiceLoss()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bce_loss = self.bce(pred, target)
        dice_loss = self.dice(pred, target)
        return self.bce_weight * bce_loss + self.dice_weight * dice_loss


# ============================================================================
# 评估指标
# ============================================================================

class MetricsTracker:
    """训练指标追踪器"""

    def __init__(self):
        self.history = {
            'train_loss': [], 'val_loss': [],
            'train_iou': [], 'val_iou': [],
            'train_dice': [], 'val_dice': [],
            'train_acc': [], 'val_acc': [],
            'train_precision': [], 'val_precision': [],
            'train_recall': [], 'val_recall': [],
        }
        self.best_val_loss = float('inf')
        self.best_epoch = 0

    def record_epoch(self, train_metrics: dict, val_metrics: dict):
        for key in self.history:
            if key.startswith('train_') and key in train_metrics:
                self.history[key].append(train_metrics[key])
            elif key.startswith('val_') and key in val_metrics:
                self.history[key].append(val_metrics[key])

    def is_best(self, val_loss: float) -> bool:
        if val_loss < self.best_val_loss:
            self.best_val_loss = val_loss
            return True
        return False


def compute_metrics(pred: torch.Tensor, target: torch.Tensor, smooth: float = 1e-6) -> dict:
    """
    计算所有分割指标

    参数:
        pred:   预测概率图 (B, 1, H, W), 值域 [0, 1]
        target: 真实 mask   (B, 1, H, W), 值域 {0, 1}
    """
    # 二值化预测
    pred_bin = (pred > 0.5).float()
    target_flat = target.view(-1)
    pred_flat = pred.view(-1)
    pred_bin_flat = pred_bin.view(-1)

    # 统计
    tp = (pred_bin_flat * target_flat).sum().item()
    fp = (pred_bin_flat * (1 - target_flat)).sum().item()
    fn = ((1 - pred_bin_flat) * target_flat).sum().item()
    tn = ((1 - pred_bin_flat) * (1 - target_flat)).sum().item()

    # IoU
    iou = tp / (tp + fp + fn + smooth)

    # Dice
    dice = 2 * tp / (2 * tp + fp + fn + smooth)

    # Pixel Accuracy
    acc = (tp + tn) / (tp + tn + fp + fn + smooth)

    # Precision
    precision = tp / (tp + fp + smooth)

    # Recall
    recall = tp / (tp + fn + smooth)

    return {
        'iou': iou,
        'dice': dice,
        'acc': acc,
        'precision': precision,
        'recall': recall,
    }


# ============================================================================
# 训练 & 验证
# ============================================================================

def train_one_epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: str,
) -> dict:
    """训练一个 epoch"""
    model.train()
    total_loss = 0.0
    all_metrics = []

    for batch in loader:
        images = batch['image'].to(device)
        masks = batch['mask'].to(device)

        optimizer.zero_grad()
        preds = model(images)
        loss = criterion(preds, masks)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        all_metrics.append(compute_metrics(preds.detach(), masks))

    n = len(all_metrics)
    return {
        'train_loss': total_loss / n,
        'train_iou': sum(m['iou'] for m in all_metrics) / n,
        'train_dice': sum(m['dice'] for m in all_metrics) / n,
        'train_acc': sum(m['acc'] for m in all_metrics) / n,
        'train_precision': sum(m['precision'] for m in all_metrics) / n,
        'train_recall': sum(m['recall'] for m in all_metrics) / n,
    }


@torch.no_grad()
def validate(model: nn.Module, loader, criterion: nn.Module, device: str) -> dict:
    """验证"""
    model.eval()
    total_loss = 0.0
    all_metrics = []

    for batch in loader:
        images = batch['image'].to(device)
        masks = batch['mask'].to(device)

        preds = model(images)
        loss = criterion(preds, masks)

        total_loss += loss.item()
        all_metrics.append(compute_metrics(preds, masks))

    n = len(all_metrics)
    return {
        'val_loss': total_loss / n,
        'val_iou': sum(m['iou'] for m in all_metrics) / n,
        'val_dice': sum(m['dice'] for m in all_metrics) / n,
        'val_acc': sum(m['acc'] for m in all_metrics) / n,
        'val_precision': sum(m['precision'] for m in all_metrics) / n,
        'val_recall': sum(m['recall'] for m in all_metrics) / n,
    }


# ============================================================================
# 主训练流程
# ============================================================================

def train(config: TrainConfig = None):
    """
    完整训练流程
    """
    if config is None:
        config = train_config

    # ---- 设置 ----
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    device = config.device

    print('=' * 55)
    print('  UNet 光伏热斑分割 - 模型训练')
    print('=' * 55)
    print(f'  数据目录: {config.data_dir}')
    print(f'  图像尺寸: {config.image_size}')
    print(f'  Epochs:   {config.epochs}')
    print(f'  Batch:    {config.batch_size}')
    print(f'  LR:       {config.learning_rate}')
    print(f'  设备:     {device}')
    print('=' * 55)

    # ---- 数据 ----
    train_loader, val_loader, test_loader = create_dataloaders(
        data_dir=config.data_dir,
        image_size=config.image_size,
        batch_size=config.batch_size,
        input_channels=config.input_channels,
    )
    print(f'  训练集: {len(train_loader.dataset)} 张')
    print(f'  验证集: {len(val_loader.dataset)} 张')

    # ---- 模型 ----
    model = create_model(
        in_channels=config.input_channels,
        base_channels=config.base_channels,
    ).to(device)
    print(f'  模型参数量: {count_parameters(model):,}')
    print('=' * 55)

    # ---- 损失函数 & 优化器 ----
    criterion = CombinedLoss(
        bce_weight=config.bce_weight,
        dice_weight=config.dice_weight,
    ).to(device)

    optimizer = optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    scheduler = ReduceLROnPlateau(
        optimizer, mode='min',
        factor=config.lr_scheduler_factor,
        patience=config.lr_scheduler_patience,
    )

    # ---- 训练循环 ----
    tracker = MetricsTracker()
    early_stop_counter = 0
    t_start = time.time()

    for epoch in range(1, config.epochs + 1):
        epoch_start = time.time()

        train_metrics = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_metrics = validate(model, val_loader, criterion, device)
        tracker.record_epoch(train_metrics, val_metrics)

        # 学习率调度
        scheduler.step(val_metrics['val_loss'])

        # 早停判断
        if tracker.is_best(val_metrics['val_loss']):
            early_stop_counter = 0
            torch.save(model.state_dict(), config.model_save_path)
            tracker.best_epoch = epoch
        else:
            early_stop_counter += 1

        # 日志
        epoch_time = time.time() - epoch_start
        print(
            f'Epoch {epoch:3d}/{config.epochs} | '
            f'Loss: {train_metrics["train_loss"]:.4f}/{val_metrics["val_loss"]:.4f} | '
            f'IoU: {val_metrics["val_iou"]:.4f} | '
            f'Dice: {val_metrics["val_dice"]:.4f} | '
            f'Acc: {val_metrics["val_acc"]:.4f} | '
            f'Time: {epoch_time:.1f}s'
            + (' ★' if tracker.is_best(val_metrics['val_loss']) else '')
        )

        # 早停触发
        if early_stop_counter >= config.early_stop_patience:
            print(f'\n早停: 连续 {config.early_stop_patience} 轮无改善，停止训练')
            break

    # ---- 训练完成 ----
    total_time = time.time() - t_start
    print(f'\n训练完成！总耗时: {total_time:.0f}s ({total_time / 60:.1f} 分钟)')
    print(f'最佳模型: epoch {tracker.best_epoch}, Val Loss = {tracker.best_val_loss:.4f}')

    # 加载最佳模型
    model.load_state_dict(torch.load(config.model_save_path, map_location=device))

    # ---- 生成可视化 ----
    print(f'\n生成训练趋势图...')
    plot_training_curves(tracker.history, config.plots_dir)

    # 生成样本预测对比
    print(f'生成样本预测图...')
    plot_sample_predictions(model, val_loader, config.plots_dir, device)

    # 打印最佳指标
    best_dict = print_best_metrics(tracker.history)

    # ---- 导出 ONNX ----
    print(f'\n导出 ONNX 模型...')
    model.eval()
    dummy_input = torch.randn(1, config.input_channels,
                              config.image_size[0], config.image_size[1]).to(device)

    try:
        torch.onnx.export(
            model,
            dummy_input,
            config.onnx_save_path,
            input_names=['input'],
            output_names=['output'],
        )
        print(f'ONNX 模型已保存到: {config.onnx_save_path}')
    except Exception as e:
        print(f'ONNX 导出失败: {e}')
        print('提示: Windows 下可能需要设置环境变量 PYTHONIOENCODING=utf-8')
        # 尝试用旧版 API 导出
        import os
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    # ---- 保存训练历史 JSON ----
    history_path = Path(config.plots_dir) / 'training_history.json'
    # 转换 numpy 类型为 Python 原生类型
    serializable_history = {}
    for k, v in tracker.history.items():
        serializable_history[k] = [float(x) for x in v]
    history_path.write_text(
        json.dumps(serializable_history, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    # ---- 保存模型信息摘要 ----
    summary_path = Path(config.plots_dir) / 'model_summary.json'
    summary = {
        'framework': 'PyTorch',
        'architecture': 'UNet',
        'parameters': count_parameters(model),
        'input_size': [config.input_channels, *config.image_size],
        'best_metrics': {k: float(v) for k, v in best_dict.items()},
        'training_time_seconds': round(total_time, 1),
        'total_epochs': len(tracker.history['train_loss']),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    print(f'\n全部文件:')
    print(f'  模型权重:  {config.model_save_path}')
    print(f'  ONNX 模型: {config.onnx_save_path}')
    print(f'  趋势图:    {config.plots_dir}/')
    print(f'  训练历史:  {history_path}')
    print(f'  模型摘要:  {summary_path}')
    print('=' * 55)

    return model, tracker.history


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='UNet 光伏热斑分割模型训练',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--epochs', type=int, default=train_config.epochs)
    parser.add_argument('--batch-size', type=int, default=train_config.batch_size)
    parser.add_argument('--lr', type=float, default=train_config.learning_rate)
    parser.add_argument('--data-dir', type=str, default=train_config.data_dir)
    parser.add_argument('--device', type=str, default=train_config.device,
                        choices=['cpu', 'cuda'])
    parser.add_argument('--base-channels', type=int, default=train_config.base_channels,
                        help=f'UNet 第一层通道数, 32=轻量~9M, 64=标准~37M (默认: {train_config.base_channels})')
    parser.add_argument('--seed', type=int, default=train_config.seed)

    args = parser.parse_args()

    # 覆盖配置
    config = TrainConfig(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        device=args.device,
        seed=args.seed,
        base_channels=args.base_channels,
    )

    train(config)


if __name__ == '__main__':
    main()
