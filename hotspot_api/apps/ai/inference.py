"""
ONNX 推理脚本
------------
加载训练好的 ONNX 模型，对红外图像进行热斑分割推理。

对外接口（黎志伟调用）:
    from apps.ai.inference import inference
    annotated_bytes = inference(image_bytes)

使用方式:
    # 作为模块
    from apps.ai.inference import inference, load_model, predict

    # 命令行测试
    python inference.py --test
    python inference.py --image path/to/thermal.jpg
"""
import base64
import io
import json
import sys
import time
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
from PIL import Image, ImageDraw

# 将 ai 目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ============================================================================
# ONNX 模型加载
# ============================================================================

class ONNXInferenceEngine:
    """
    ONNX 推理引擎（单例）

    用法:
        engine = ONNXInferenceEngine()
        engine.load('model.onnx')
        mask = engine.predict(image_np)
    """

    def __init__(self):
        self._session = None
        self._input_name = None
        self._output_name = None
        self._input_size = None
        self._loaded = False

    def load(self, model_path: str = None):
        """加载 ONNX 模型"""
        import onnxruntime as ort

        if model_path is None:
            from config import inference_config
            model_path = inference_config.onnx_model_path

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f'ONNX 模型文件不存在: {model_path}\n'
                f'请先运行 train.py 训练并导出模型。'
            )

        # 设置执行提供器（优先 GPU）
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self._session = ort.InferenceSession(str(model_path), providers=providers)

        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name
        input_shape = self._session.get_inputs()[0].shape
        self._input_size = (input_shape[2], input_shape[3])  # (H, W)
        self._loaded = True

        provider = self._session.get_providers()[0]
        print(f'[ONNX] 模型已加载: {model_path}')
        print(f'[ONNX] 输入尺寸: {self._input_size}')
        print(f'[ONNX] 执行提供器: {provider}')

    def predict(self, image_np: np.ndarray) -> np.ndarray:
        """
        对单张图像进行推理

        参数:
            image_np: numpy 数组 (H, W) 灰度或 (H, W, C) RGB

        返回:
            mask: numpy 数组 (H, W)，float32，值域 [0, 1]
        """
        if not self._loaded:
            raise RuntimeError('模型未加载，请先调用 load()')

        # 预处理
        if image_np.ndim == 3:
            # RGB → 灰度
            image_np = np.mean(image_np, axis=2).astype(np.float32)
        elif image_np.ndim == 2:
            image_np = image_np.astype(np.float32)
        else:
            raise ValueError(f'不支持的图像维度: {image_np.ndim}')

        # 缩放到模型输入尺寸
        h, w = image_np.shape
        if (h, w) != self._input_size:
            pil_img = Image.fromarray(image_np.astype(np.uint8))
            pil_img = pil_img.resize(
                (self._input_size[1], self._input_size[0]), Image.BILINEAR
            )
            image_np = np.array(pil_img, dtype=np.float32)

        # 归一化 [0, 255] → [0, 1]
        if image_np.max() > 1.0:
            image_np = image_np / 255.0

        # 转为 (1, 1, H, W) 的 float32 tensor
        input_tensor = image_np[np.newaxis, np.newaxis, :, :].astype(np.float32)

        # 推理
        output = self._session.run(
            [self._output_name], {self._input_name: input_tensor}
        )[0]

        # 输出: (1, 1, H, W) → (H, W)
        mask = output[0, 0, :, :]
        return mask

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# 全局引擎实例（懒加载）
_engine: Optional[ONNXInferenceEngine] = None


def get_engine() -> ONNXInferenceEngine:
    """获取全局推理引擎（自动加载模型）"""
    global _engine
    if _engine is None:
        _engine = ONNXInferenceEngine()
        _engine.load()
    return _engine


# ============================================================================
# 对外接口
# ============================================================================

def inference(image_bytes: bytes, threshold: float = 0.5) -> bytes:
    """
    对外推理接口（黎志伟在 process_image() 中调用此函数）

    参数:
        image_bytes: 红外原图 bytes（PNG / JPEG / PPM）
        threshold:   二值化阈值（概率 ≥ threshold 视为热斑，默认 0.5）

    返回:
        annotated_bytes: AI 标注图 bytes（PNG 格式，热斑区域红色标注叠加）
    """
    from config import inference_config

    # 1. 解码图像
    image = Image.open(io.BytesIO(image_bytes))
    original_size = image.size  # (W, H)

    # 转灰度 numpy
    image_np = np.array(image.convert('L'))  # (H, W)

    # 2. AI 推理
    engine = get_engine()
    mask = engine.predict(image_np)  # (H, W), [0, 1]

    # 3. 后处理：二值化
    mask_bin = (mask >= threshold).astype(np.uint8) * 255

    # 4. 缩放 mask 回原始图像尺寸
    mask_pil = Image.fromarray(mask_bin)
    mask_pil = mask_pil.resize(original_size, Image.NEAREST)

    # 5. 在原图上叠加标注
    image_rgb = image.convert('RGB')
    overlay = Image.new('RGBA', image_rgb.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    mask_array = np.array(mask_pil)
    hot_spot_coords = np.where(mask_array > 127)

    if len(hot_spot_coords[0]) > 0:
        # 用半透明红色填充热斑区域
        for y, x in zip(hot_spot_coords[0], hot_spot_coords[1]):
            overlay.putpixel(
                (x, y),
                (255, 0, 0, int(255 * inference_config.overlay_alpha)),
            )

    image_rgb = Image.alpha_composite(image_rgb.convert('RGBA'), overlay).convert('RGB')

    # 6. 编码为 bytes 返回
    output_buffer = io.BytesIO()
    image_rgb.save(output_buffer, format='PNG')
    return output_buffer.getvalue()


def predict_mask(image_bytes: bytes) -> np.ndarray:
    """
    只返回分割 mask（不做标注叠加）

    参数:
        image_bytes: 红外原图 bytes

    返回:
        mask: numpy 数组 (H, W)，float32，值域 [0, 1]
    """
    image = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image.convert('L'))
    engine = get_engine()
    return engine.predict(image_np)


# ============================================================================
# 性能测试
# ============================================================================

def benchmark(num_runs: int = 100):
    """推理延迟基准测试"""
    from config import inference_config

    engine = get_engine()
    h, w = engine._input_size
    dummy = np.random.randint(0, 255, (h, w), dtype=np.uint8)

    # 预热
    for _ in range(10):
        engine.predict(dummy)

    # 计时
    times = []
    for _ in range(num_runs):
        t0 = time.perf_counter()
        engine.predict(dummy)
        times.append((time.perf_counter() - t0) * 1000)  # ms

    times = np.array(times)
    print(f'\n推理性能基准测试 ({num_runs} 次):')
    print(f'  平均延迟:  {times.mean():.1f} ms')
    print(f'  最小延迟:  {times.min():.1f} ms')
    print(f'  最大延迟:  {times.max():.1f} ms')
    print(f'  P95 延迟:  {np.percentile(times, 95):.1f} ms')
    print(f'  FPS:       {1000 / times.mean():.1f}')


# ============================================================================
# CLI 测试
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='ONNX 推理测试')
    parser.add_argument('--image', type=str, help='输入红外图像路径')
    parser.add_argument('--test', action='store_true', help='使用随机数据测试')
    parser.add_argument('--benchmark', action='store_true', help='运行性能基准测试')
    parser.add_argument('--model', type=str, default=None, help='ONNX 模型路径')
    args = parser.parse_args()

    if args.benchmark:
        # 加载模型
        if args.model:
            global _engine
            _engine = ONNXInferenceEngine()
            _engine.load(args.model)
        benchmark()
        return

    if args.image:
        # 单张图片推理
        image_path = Path(args.image)
        if not image_path.exists():
            print(f'文件不存在: {image_path}')
            sys.exit(1)

        image_bytes = image_path.read_bytes()
        result_bytes = inference(image_bytes)

        out_path = image_path.parent / f'{image_path.stem}_annotated.png'
        out_path.write_bytes(result_bytes)
        print(f'标注图已保存: {out_path}')
        return

    if args.test:
        # 生成一张模拟红外图测试
        from generate_synthetic import generate_single_sample

        print('生成模拟红外图...')
        rgb_img, mask_img, num_hs = generate_single_sample()

        buf = io.BytesIO()
        rgb_img.save(buf, format='PNG')
        test_bytes = buf.getvalue()

        print(f'热斑数: {num_hs}')

        try:
            result_bytes = inference(test_bytes)
            out_path = Path(__file__).resolve().parent / 'test_result.png'
            out_path.write_bytes(result_bytes)
            print(f'推理结果已保存: {out_path}')
        except FileNotFoundError as e:
            print(f'推理失败: {e}')
            print('请先训练模型: python train.py')
        return

    parser.print_help()


if __name__ == '__main__':
    main()
