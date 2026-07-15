"""
数据加载模块
-----------
继承 torch.utils.data.Dataset，加载红外图 + mask 配对数据，
支持数据增强（albumentations）。
"""
import random
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
from PIL import Image

import torch
from torch.utils.data import Dataset, DataLoader

# albumentations 是可选的（允许无此包时仍能 import）
try:
    import albumentations as A
    HAS_ALBUMENTATIONS = True
except ImportError:
    HAS_ALBUMENTATIONS = False


# ============================================================================
# Dataset
# ============================================================================

class ThermalHotspotDataset(Dataset):
    """
    光伏红外热斑分割数据集

    目录结构要求:
        root_dir/
        ├── images/    # 红外原图 (PNG/JPG)，文件名如 001.png
        └── masks/     # 标注 mask (PNG)，文件名与 images 一致

    mask 约定:
        - 像素值 0   = 背景（正常区域）
        - 像素值 255 = 热斑区域
        - 会自动归一化到 [0, 1]
    """

    def __init__(
        self,
        root_dir: str,
        image_size: Tuple[int, int] = (192, 256),  # H×W
        augment: bool = False,
        input_channels: int = 1,
    ):
        self.root_dir = Path(root_dir)
        self.image_size = image_size
        self.augment = augment and HAS_ALBUMENTATIONS
        self.input_channels = input_channels

        self.images_dir = self.root_dir / 'images'
        self.masks_dir = self.root_dir / 'masks'

        # 收集所有图像文件
        self.image_paths = sorted(
            p for p in self.images_dir.glob('*')
            if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        )

        if not self.image_paths:
            raise FileNotFoundError(
                f'在 {self.images_dir} 中未找到图像文件！\n'
                f'请先运行 generate_synthetic.py 或放入数据集。'
            )

        # 验证 mask 文件存在
        self._valid_paths = []
        for img_path in self.image_paths:
            mask_path = self.masks_dir / img_path.name
            if mask_path.exists():
                self._valid_paths.append((img_path, mask_path))

        if not self._valid_paths:
            raise FileNotFoundError(
                f'在 {self.masks_dir} 中未找到匹配的 mask 文件！\n'
                f'请确保 images/ 和 masks/ 中的文件名一一对应。'
            )

    def __len__(self) -> int:
        return len(self._valid_paths)

    def __getitem__(self, idx: int) -> dict:
        img_path, mask_path = self._valid_paths[idx]

        # 读取图像
        image = Image.open(img_path)
        mask = Image.open(mask_path).convert('L')  # 灰度

        # 转为 numpy
        image_np = np.array(image)      # H×W 或 H×W×C
        mask_np = np.array(mask)        # H×W

        # 统一通道数
        if image_np.ndim == 2:
            image_np = image_np[:, :, np.newaxis]  # H×W×1
        elif image_np.ndim == 3 and image_np.shape[2] > self.input_channels:
            image_np = image_np[:, :, :self.input_channels]

        # 缩放到目标尺寸
        image_pil = Image.fromarray(image_np.squeeze() if image_np.shape[2] == 1 else image_np)
        mask_pil = Image.fromarray(mask_np)

        image_pil = image_pil.resize(
            (self.image_size[1], self.image_size[0]), Image.BILINEAR
        )
        mask_pil = mask_pil.resize(
            (self.image_size[1], self.image_size[0]), Image.NEAREST
        )

        image_np = np.array(image_pil)
        mask_np = np.array(mask_pil)

        if image_np.ndim == 2:
            image_np = image_np[:, :, np.newaxis]

        # 数据增强
        if self.augment:
            transformed = self._augment(image_np, mask_np)
            image_np = transformed['image']
            mask_np = transformed['mask']

        # 归一化 image: [0, 255] → [0, 1]
        image_np = image_np.astype(np.float32) / 255.0

        # 归一化 mask: 0/255 → 0.0/1.0，二值化
        mask_np = (mask_np > 127).astype(np.float32)

        # 转为 tensor: (H, W, C) → (C, H, W)
        image_tensor = torch.from_numpy(image_np).permute(2, 0, 1)
        mask_tensor = torch.from_numpy(mask_np).unsqueeze(0)   # (1, H, W)

        return {
            'image': image_tensor,
            'mask': mask_tensor,
            'filename': img_path.name,
        }

    def _augment(self, image: np.ndarray, mask: np.ndarray) -> dict:
        """数据增强 pipeline"""
        transforms = A.Compose([
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.3),
            A.Affine(
                scale=(0.9, 1.1), translate_percent=(0, 0.05),
                rotate=(-15, 15), p=0.5,
            ),
            A.RandomBrightnessContrast(
                brightness_limit=0.1, contrast_limit=0.1, p=0.5
            ),
            A.GaussNoise(std_range=(0.04, 0.08), p=0.3),
        ])
        result = transforms(image=image, mask=mask)
        return result


# ============================================================================
# DataLoader 工厂
# ============================================================================

def create_dataloaders(
    data_dir: str,
    image_size: Tuple[int, int] = (192, 256),
    batch_size: int = 8,
    input_channels: int = 1,
    num_workers: int = 0,  # Windows 下建议 0
) -> Tuple[DataLoader, DataLoader, Optional[DataLoader]]:
    """
    创建训练/验证/测试 DataLoader

    返回: (train_loader, val_loader, test_loader)
    test_loader 在 test/ 目录不存在时返回 None
    """
    train_dir = Path(data_dir) / 'train'
    val_dir = Path(data_dir) / 'val'
    test_dir = Path(data_dir) / 'test'

    if not train_dir.exists():
        raise FileNotFoundError(f'训练数据目录不存在: {train_dir}')

    train_dataset = ThermalHotspotDataset(
        root_dir=str(train_dir),
        image_size=image_size,
        augment=True,
        input_channels=input_channels,
    )

    val_dataset = ThermalHotspotDataset(
        root_dir=str(val_dir) if val_dir.exists() else str(train_dir),
        image_size=image_size,
        augment=False,
        input_channels=input_channels,
    )

    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True, drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True,
    )

    test_loader = None
    if test_dir.exists():
        test_dataset = ThermalHotspotDataset(
            root_dir=str(test_dir),
            image_size=image_size,
            augment=False,
            input_channels=input_channels,
        )
        test_loader = DataLoader(
            test_dataset, batch_size=1, shuffle=False,
            num_workers=0,
        )

    return train_loader, val_loader, test_loader


# ============================================================================
# 自测
# ============================================================================

if __name__ == '__main__':
    import sys
    from pathlib import Path

    data_dir = Path(__file__).resolve().parent / 'data' / 'train'
    if not data_dir.exists():
        print(f'数据目录不存在: {data_dir}')
        print('请先运行 generate_synthetic.py 生成模拟数据')
        sys.exit(1)

    ds = ThermalHotspotDataset(str(data_dir))
    print(f'数据集大小: {len(ds)}')
    sample = ds[0]
    print(f'图像 shape: {sample["image"].shape}')
    print(f'Mask  shape: {sample["mask"].shape}')
    print(f'Mask 唯一值: {sample["mask"].unique().tolist()}')
    print(f'文件名: {sample["filename"]}')
