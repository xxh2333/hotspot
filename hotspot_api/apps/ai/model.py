"""
UNet 图像分割模型
--------------
经典 UNet 架构，用于光伏红外热斑分割。
输入: 单通道灰度红外图 (B, 1, H, W)
输出: 单通道热斑概率 mask (B, 1, H, W)，值域 [0, 1]
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================================
# 基础模块
# ============================================================================

class DoubleConv(nn.Module):
    """两次卷积 + BN + ReLU"""

    def __init__(self, in_channels: int, out_channels: int, mid_channels: int = None):
        super().__init__()
        mid_channels = mid_channels or out_channels
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class Down(nn.Module):
    """下采样：MaxPool → DoubleConv"""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.pool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pool_conv(x)


class Up(nn.Module):
    """上采样：转置卷积/Upsample → 拼接 skip → DoubleConv"""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        # 使用双线性插值 + 1x1 卷积，比转置卷积更平滑
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        x1 = self.up(x1)
        # 处理尺寸不匹配（H 或 W 差 1 像素）
        diff_h = x2.size(2) - x1.size(2)
        diff_w = x2.size(3) - x1.size(3)
        x1 = F.pad(x1, [diff_w // 2, diff_w - diff_w // 2,
                        diff_h // 2, diff_h - diff_h // 2])
        x = torch.cat([x2, x1], dim=1)  # skip connection
        return self.conv(x)


# ============================================================================
# UNet 主模型
# ============================================================================

class UNet(nn.Module):
    """
    UNet 图像分割网络

    架构:
      encoder:  1→64→128→256→512
      bottleneck: 512→1024
      decoder:  1024→512→256→128→64 → 1 (sigmoid)

    参数:
        n_channels: 输入通道数，默认 1（灰度红外图）
        n_classes:  输出通道数，默认 1（二值分割）
        base_channels: 第一层通道数，默认 64
    """

    def __init__(self, n_channels: int = 1, n_classes: int = 1, base_channels: int = 64):
        super().__init__()

        self.n_channels = n_channels
        self.n_classes = n_classes

        # ---- Encoder ----
        self.inc = DoubleConv(n_channels, base_channels)               # → C×H×W
        self.down1 = Down(base_channels, base_channels * 2)            # → 2C×H/2×W/2
        self.down2 = Down(base_channels * 2, base_channels * 4)        # → 4C×H/4×W/4
        self.down3 = Down(base_channels * 4, base_channels * 8)        # → 8C×H/8×W/8

        # ---- Bottleneck ----
        self.bottleneck = DoubleConv(base_channels * 8, base_channels * 16)  # → 16C×H/8×W/8

        # ---- Decoder ----
        # in_channels = 上采样后的通道数 + skip 连接的通道数
        self.up1 = Up(base_channels * 24, base_channels * 8)            # 1024+512=1536 → 512
        self.up2 = Up(base_channels * 12, base_channels * 4)            # 512+256=768 → 256
        self.up3 = Up(base_channels * 6, base_channels * 2)             # 256+128=384 → 128
        self.up4 = Up(base_channels * 3, base_channels)                 # 128+64=192 → 64

        # ---- 输出头 ----
        self.outc = nn.Conv2d(base_channels, n_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        x1 = self.inc(x)       # 64
        x2 = self.down1(x1)    # 128
        x3 = self.down2(x2)    # 256
        x4 = self.down3(x3)    # 512

        # Bottleneck
        x5 = self.bottleneck(x4)  # 1024

        # Decoder (with skip connections)
        x = self.up1(x5, x4)   # 512
        x = self.up2(x, x3)    # 256
        x = self.up3(x, x2)    # 128
        x = self.up4(x, x1)    # 64

        # Output
        logits = self.outc(x)
        return torch.sigmoid(logits)


# ============================================================================
# 工具函数
# ============================================================================

def count_parameters(model: nn.Module) -> int:
    """统计可训练参数数量"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def create_model(in_channels: int = 1, base_channels: int = 64) -> UNet:
    """工厂函数：创建 UNet 模型"""
    model = UNet(n_channels=in_channels, n_classes=1, base_channels=base_channels)
    return model


# ============================================================================
# 自测
# ============================================================================

if __name__ == '__main__':
    model = create_model(in_channels=1, base_channels=64)
    print(f"UNet 参数量: {count_parameters(model):,}")

    # 模拟输入：(batch=2, channel=1, H=192, W=256)
    dummy_input = torch.randn(2, 1, 192, 256)
    with torch.no_grad():
        output = model(dummy_input)
    print(f"输入 shape:  {dummy_input.shape}")
    print(f"输出 shape:  {output.shape}")
    print(f"输出值范围: [{output.min().item():.4f}, {output.max().item():.4f}]")

    # 测试 ONNX 导出兼容性
    try:
        torch.onnx.export(
            model,
            torch.randn(1, 1, 192, 256),
            'test_model.onnx',
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},
            opset_version=12,
        )
        print("ONNX 导出测试通过 ✓")
        import os
        os.remove('test_model.onnx')
    except (ModuleNotFoundError, ImportError) as e:
        print(f"ONNX 导出跳过（缺少依赖: {e}）")
