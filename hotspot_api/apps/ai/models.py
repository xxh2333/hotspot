"""
AI 模块数据模型
---------------
模型性能指标存储 + 模型元信息
"""
from django.db import models


class ModelInfo(models.Model):
    """
    AI 模型元信息表
    记录当前部署模型的版本、架构、训练信息
    """
    model_name = models.CharField(max_length=64, default='UNet', verbose_name='模型名称')
    model_version = models.CharField(max_length=32, default='1.0.0', verbose_name='模型版本')
    framework = models.CharField(max_length=32, default='PyTorch → ONNX', verbose_name='训练/推理框架')
    architecture = models.CharField(max_length=64, default='UNet', verbose_name='网络架构')
    input_size = models.CharField(max_length=32, default='256×192', verbose_name='输入尺寸')
    base_channels = models.IntegerField(default=32, verbose_name='基础通道数')
    dataset_size = models.IntegerField(default=2000, verbose_name='训练样本数')
    epochs = models.IntegerField(default=100, verbose_name='训练轮数')
    description = models.TextField(blank=True, null=True, verbose_name='补充说明')
    deployed_at = models.DateTimeField(auto_now_add=True, verbose_name='部署时间')

    class Meta:
        db_table = 'ai_model_info'
        verbose_name = 'AI 模型信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.model_name} v{self.model_version}'


class PerformanceMetrics(models.Model):
    """
    AI 模型性能指标表
    存储验证集上的各项分割指标 + 推理性能
    """
    iou = models.FloatField(verbose_name='IoU (交并比)')
    dice = models.FloatField(verbose_name='Dice 系数')
    pixel_accuracy = models.FloatField(verbose_name='像素准确率')
    precision = models.FloatField(verbose_name='精确率 (Precision)')
    recall = models.FloatField(verbose_name='召回率 (Recall)')
    inference_latency_ms = models.FloatField(verbose_name='推理延迟 (ms)')
    fps = models.FloatField(verbose_name='FPS (每秒帧数)')
    eval_dataset_size = models.IntegerField(default=200, verbose_name='验证集样本数')
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')

    class Meta:
        db_table = 'ai_performance_metrics'
        verbose_name = 'AI 性能指标'
        verbose_name_plural = verbose_name
        ordering = ['-recorded_at']

    def __str__(self):
        return f'[metrics] IoU={self.iou:.3f} Dice={self.dice:.3f} Latency={self.inference_latency_ms:.1f}ms'
