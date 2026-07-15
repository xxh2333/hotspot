"""
AI 模型训练和推理的统一配置
"""
from dataclasses import dataclass, field
from pathlib import Path


# 项目根目录（ai app 所在位置）
AI_APP_DIR = Path(__file__).resolve().parent


@dataclass
class TrainConfig:
    """训练超参数配置"""

    # --- 数据 ---
    data_dir: str = str(AI_APP_DIR / 'data')
    image_size: tuple = (192, 256)  # H×W，与当前红外图匹配
    input_channels: int = 1          # 灰度图 1 通道
    base_channels: int = 32          # UNet 第一层通道数 (32=轻量 ~9M, 64=标准 ~37M)

    # --- 训练 ---
    epochs: int = 100
    batch_size: int = 8
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5

    # --- 损失函数权重 ---
    bce_weight: float = 0.5
    dice_weight: float = 0.5

    # --- 学习率调度 ---
    lr_scheduler_patience: int = 10
    lr_scheduler_factor: float = 0.5

    # --- 早停 ---
    early_stop_patience: int = 20

    # --- 保存 ---
    model_save_path: str = str(AI_APP_DIR / 'model.pth')
    onnx_save_path: str = str(AI_APP_DIR / 'model.onnx')
    plots_dir: str = str(AI_APP_DIR / 'training_plots')

    # --- 设备 ---
    device: str = 'cpu'  # 'cuda' / 'cpu'

    # --- 随机种子 ---
    seed: int = 42


@dataclass
class InferenceConfig:
    """ONNX 推理配置"""

    onnx_model_path: str = str(AI_APP_DIR / 'model.onnx')
    input_size: tuple = (192, 256)  # H×W
    threshold: float = 0.5           # 二值化阈值（概率 >= threshold → 热斑）
    overlay_alpha: float = 0.4       # 标注叠加透明度


# 默认实例
train_config = TrainConfig()
inference_config = InferenceConfig()
