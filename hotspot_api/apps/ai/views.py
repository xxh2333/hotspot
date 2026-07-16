"""
AI + MQTT API 视图
-------------------
  GET  /api/ai/model-info      → AI 模型元信息
  GET  /api/ai/metrics         → AI 模型性能指标
  GET  /api/mqtt/status        → MQTT 连接状态
  GET  /api/mqtt/messages      → MQTT 消息实时日志 (SSE)
"""
import json
import queue
import time
import uuid
import logging

from django.http import StreamingHttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import ModelInfo, PerformanceMetrics
from apps.monitor.serializers import APIResponse

logger = logging.getLogger('ai.views')


# ============================================================================
# 1. AI 模型信息
# ============================================================================

class ModelInfoView(APIView):
    """GET /api/ai/model-info — 当前部署模型的元信息"""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            info = ModelInfo.objects.order_by('-deployed_at').first()
            if info is None:
                return Response(APIResponse.ok({
                    'model_name': 'UNet',
                    'model_version': '1.0.0',
                    'framework': 'PyTorch → ONNX',
                    'architecture': 'UNet (轻量版)',
                    'input_size': '256×192',
                    'base_channels': 32,
                    'dataset_size': 2000,
                    'training_epochs': 100,
                    'description': '光伏热斑语义分割模型，输入单通道红外灰度图，输出逐像素热斑概率mask',
                }))

            return Response(APIResponse.ok({
                'model_name': info.model_name,
                'model_version': info.model_version,
                'framework': info.framework,
                'architecture': info.architecture,
                'input_size': info.input_size,
                'base_channels': info.base_channels,
                'dataset_size': info.dataset_size,
                'training_epochs': info.epochs,
                'description': info.description or '',
                'deployed_at': timezone.localtime(info.deployed_at).isoformat(),
            }))
        except Exception as e:
            return Response(APIResponse.fail(50001, str(e)))


# ============================================================================
# 2. AI 性能指标
# ============================================================================

class PerformanceMetricsView(APIView):
    """GET /api/ai/metrics — 最新模型性能指标"""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            metrics = PerformanceMetrics.objects.order_by('-recorded_at').first()
            if metrics is None:
                # 返回默认值（模型已训练但指标尚未录入数据库时）
                return Response(APIResponse.ok({
                    'iou': 0.72,
                    'dice': 0.84,
                    'pixel_accuracy': 0.96,
                    'precision': 0.78,
                    'recall': 0.91,
                    'inference_latency_ms': 45.0,
                    'fps': 22.2,
                    'eval_dataset_size': 200,
                    'recorded_at': None,
                    'note': '默认参考值，请联系 AI 负责人录入真实指标',
                }))

            return Response(APIResponse.ok({
                'iou': round(metrics.iou, 4),
                'dice': round(metrics.dice, 4),
                'pixel_accuracy': round(metrics.pixel_accuracy, 4),
                'precision': round(metrics.precision, 4),
                'recall': round(metrics.recall, 4),
                'inference_latency_ms': round(metrics.inference_latency_ms, 1),
                'fps': round(metrics.fps, 1),
                'eval_dataset_size': metrics.eval_dataset_size,
                'recorded_at': timezone.localtime(metrics.recorded_at).isoformat() if metrics.recorded_at else None,
            }))
        except Exception as e:
            return Response(APIResponse.fail(50001, str(e)))


# ============================================================================
# 3. MQTT 连接状态
# ============================================================================

class MqttStatusView(APIView):
    """GET /api/mqtt/status — MQTT Broker 连接状态"""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            from apps.monitor.mqtt import mqtt_client
            from apps.monitor.services import sse_manager
            from apps.monitor.models import DeviceStatus

            # MQTT 连接状态
            connected = mqtt_client.is_connected()
            mqtt_device = DeviceStatus.objects.filter(device_type='mqtt').first()

            # 已订阅主题
            topics = [
                {'topic': 'pv/hotspot/up/status', 'direction': '上行', 'description': '温度/状态数据'},
                {'topic': 'pv/hotspot/up/image', 'direction': '上行', 'description': '红外图像帧'},
                {'topic': 'pv/hotspot/down/control', 'direction': '下行', 'description': '控制指令（分闸/合闸/复位）'},
            ]

            return Response(APIResponse.ok({
                'connected': connected,
                'broker_host': getattr(mqtt_client, '_broker_host', 'broker.emqx.io'),
                'broker_port': getattr(mqtt_client, '_broker_port', 1883),
                'client_id': 'django_backend',
                'sse_clients': sse_manager.get_connection_count(),
                'topics': topics,
                'last_seen': mqtt_device.last_seen.isoformat() if mqtt_device and mqtt_device.last_seen else None,
            }))
        except Exception as e:
            return Response(APIResponse.fail(50001, str(e)))


# ============================================================================
# 4. MQTT 消息日志 SSE 流
# ============================================================================

class MqttMessagesStreamView(View):
    """
    GET /api/mqtt/messages?token=<jwt>
    MQTT 消息实时日志 SSE 流
    实时推送最近收到的 MQTT 消息摘要
    """
    def get(self, request):
        token = request.GET.get('token')
        if not token:
            return JsonResponse(APIResponse.fail(40002, '缺少认证参数: token'), status=400)

        # JWT 验证
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        try:
            jwt_auth = JWTAuthentication()
            validated = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated)
            if user is None or not user.is_active:
                return JsonResponse(APIResponse.fail(40001, 'Token 无效'), status=400)
        except (InvalidToken, TokenError) as e:
            return JsonResponse(APIResponse.fail(40001, f'Token 认证失败: {e}'), status=400)

        client_id = f'mqtt-log-{user.id}-{uuid.uuid4().hex[:6]}'

        response = StreamingHttpResponse(
            self._event_generator(client_id),
            content_type='text/event-stream',
            status=200,
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def _event_generator(self, client_id: str):
        """SSE 事件生成器 — 推送 MQTT 消息日志"""
        from apps.monitor.services import sse_manager

        client_queue = queue.Queue(maxsize=256)
        sse_manager.register(client_id, client_queue)

        try:
            yield _fmt_sse('connected', json.dumps({
                'client_id': client_id,
                'message': 'MQTT 消息日志流已连接',
            }, ensure_ascii=False))

            while True:
                try:
                    msg = client_queue.get(timeout=10)
                    yield _fmt_sse(msg['event'], msg['data'])
                except queue.Empty:
                    yield _fmt_sse('heartbeat', json.dumps({
                        'timestamp': timezone.localtime(timezone.now()).isoformat(),
                    }))

        except GeneratorExit:
            pass
        except Exception as e:
            logger.error(f'MQTT SSE 异常: {e}')
        finally:
            sse_manager.unregister(client_id)


def _fmt_sse(event: str, data: str) -> bytes:
    return f'event: {event}\ndata: {data}\n\n'.encode('utf-8')
