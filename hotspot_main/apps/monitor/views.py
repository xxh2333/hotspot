"""
monitor 实时监控面板 API 视图
-------------------------------
HTTP 接口 + SSE 事件流

接口列表:
  GET  /api/dashboard/initial   - 仪表盘初始数据
  GET  /api/dashboard/stream    - SSE 实时数据流
  GET  /api/temperature/history - 历史温度数据
  GET  /api/alarms/history      - 历史告警列表
  POST /api/control/reset       - 复位（合闸）指令
  POST /api/control/trip        - 分闸指令
  POST /api/control/threshold   - 修改告警阈值
"""
import json
import queue
import threading
import logging
import uuid

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .serializers import (
    APIResponse,
    ControlResetSerializer, ControlTripSerializer, ControlResultSerializer,
    ThresholdUpdateSerializer, ThresholdResultSerializer,
)
from .services import (
    DashboardService, TemperatureHistoryService,
    AlarmService, ControlService, sse_manager,
)

logger = logging.getLogger('monitor.views')


# ============================================================================
# 错误码常量
# ============================================================================

class ErrorCode:
    SUCCESS = 0
    BAD_REQUEST = 40001
    MISSING_PARAM = 40002
    INVALID_BRANCH = 40003
    INVALID_THRESHOLD = 40004
    NOT_FOUND = 40401
    SERVER_ERROR = 50001
    DB_ERROR = 50002
    MQTT_UNAVAILABLE = 50003
    SSE_FAILED = 50004
    PI_OFFLINE = 50301


# ============================================================================
# 辅助函数
# ============================================================================

def make_response(data=None, msg='success', code=0):
    """构建统一响应格式"""
    return Response(
        APIResponse.ok(data, msg) if code == 0 else APIResponse.fail(code, msg, data),
        status=status.HTTP_200_OK if code == 0 else status.HTTP_400_BAD_REQUEST,
    )


# ============================================================================
# 1. 仪表盘初始数据
# ============================================================================

class DashboardInitialView(APIView):
    """
    GET /api/dashboard/initial
    获取仪表盘初始数据：各支路温度、断路器状态、告警统计、设备状态、阈值等
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            data = DashboardService.get_initial_data()
            return make_response(data=data)
        except Exception as e:
            logger.error(f'获取仪表盘初始数据失败: {e}', exc_info=True)
            return make_response(code=ErrorCode.SERVER_ERROR, msg=f'服务器内部错误: {str(e)}')


# ============================================================================
# 2. 历史温度数据
# ============================================================================

class TemperatureHistoryView(APIView):
    """
    GET /api/temperature/history
    获取指定时间范围内的温度历史数据
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # 参数校验
            branch = request.query_params.get('branch')
            start = request.query_params.get('start')
            end = request.query_params.get('end')
            interval = request.query_params.get('interval', 'hour')

            # 必填参数检查
            if not branch:
                return make_response(code=ErrorCode.MISSING_PARAM, msg='缺少必填参数: branch')
            if not start:
                return make_response(code=ErrorCode.MISSING_PARAM, msg='缺少必填参数: start')
            if not end:
                return make_response(code=ErrorCode.MISSING_PARAM, msg='缺少必填参数: end')

            # 支路编号校验
            try:
                branch = int(branch)
                if branch < 1 or branch > 4:
                    return make_response(code=ErrorCode.INVALID_BRANCH, msg='支路编号无效，有效值为 1~4')
            except (ValueError, TypeError):
                return make_response(code=ErrorCode.BAD_REQUEST, msg='支路编号格式错误')

            # 聚合粒度校验
            if interval not in ('hour', 'day'):
                interval = 'hour'

            data = TemperatureHistoryService.get_history(branch, start, end, interval)
            return make_response(data=data)

        except ValueError as e:
            return make_response(code=ErrorCode.BAD_REQUEST, msg=str(e))
        except Exception as e:
            logger.error(f'获取温度历史失败: {e}', exc_info=True)
            return make_response(code=ErrorCode.DB_ERROR, msg=f'数据库查询失败: {str(e)}')


# ============================================================================
# 3. 历史告警列表
# ============================================================================

class AlarmHistoryView(APIView):
    """
    GET /api/alarms/history
    获取历史告警记录列表，支持分页和多条件筛选
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            page = request.query_params.get('page', 1)
            limit = request.query_params.get('limit', 20)
            branch = request.query_params.get('branch')
            alarm_type = request.query_params.get('alarm_type')
            alarm_status = request.query_params.get('status')
            start = request.query_params.get('start')
            end = request.query_params.get('end')

            # 参数校验
            try:
                page = int(page)
                if page < 1:
                    page = 1
            except (ValueError, TypeError):
                page = 1

            try:
                limit = int(limit)
                if limit < 1:
                    limit = 20
                elif limit > 100:
                    limit = 100
            except (ValueError, TypeError):
                limit = 20

            if branch:
                try:
                    branch = int(branch)
                    if branch < 1 or branch > 4:
                        return make_response(code=ErrorCode.INVALID_BRANCH, msg='支路编号无效，有效值为 1~4')
                except (ValueError, TypeError):
                    return make_response(code=ErrorCode.BAD_REQUEST, msg='支路编号格式错误')

            if alarm_type and alarm_type not in ('hot_spot', 'over_temp', 'offline'):
                return make_response(code=ErrorCode.BAD_REQUEST, msg='告警类型无效')

            if alarm_status and alarm_status not in ('pending', 'resolved', 'recovering'):
                return make_response(code=ErrorCode.BAD_REQUEST, msg='处置状态无效')

            data = AlarmService.get_history(
                page=page, limit=limit,
                branch=branch, alarm_type=alarm_type,
                status=alarm_status, start=start, end=end,
            )
            return make_response(data=data)

        except Exception as e:
            logger.error(f'获取告警历史失败: {e}', exc_info=True)
            return make_response(code=ErrorCode.DB_ERROR, msg=f'数据库查询失败: {str(e)}')


# ============================================================================
# 4. 控制指令 - 复位（合闸）
# ============================================================================

class ControlResetView(APIView):
    """
    POST /api/control/reset
    发送断路器复位（合闸）指令
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = ControlResetSerializer(data=request.data)
            if not serializer.is_valid():
                errors = serializer.errors
                # 判断是缺少参数还是数值无效
                if 'branch' in errors:
                    for err in errors['branch']:
                        if 'required' in str(err).lower():
                            return make_response(code=ErrorCode.MISSING_PARAM, msg='缺少必填参数: branch')
                    return make_response(code=ErrorCode.INVALID_BRANCH, msg='支路编号无效，有效值为 1~4')
                return make_response(code=ErrorCode.BAD_REQUEST, msg=f'请求参数错误: {errors}')

            branch = serializer.validated_data['branch']
            operator = serializer.validated_data.get('operator', 'admin')

            result = ControlService.send_reset(branch, operator)
            return make_response(data=result, msg='复位指令已发送，断路器正在闭合')

        except ValueError as e:
            return make_response(code=ErrorCode.INVALID_BRANCH, msg=str(e))
        except ConnectionError as e:
            error_msg = str(e)
            if '不可用' in error_msg:
                return make_response(code=ErrorCode.MQTT_UNAVAILABLE, msg=error_msg)
            return make_response(code=ErrorCode.PI_OFFLINE, msg='树莓派离线')
        except Exception as e:
            logger.error(f'发送复位指令失败: {e}', exc_info=True)
            return make_response(code=ErrorCode.SERVER_ERROR, msg=f'服务器内部错误: {str(e)}')


# ============================================================================
# 5. 控制指令 - 分闸
# ============================================================================

class ControlTripView(APIView):
    """
    POST /api/control/trip
    发送断路器分闸指令
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = ControlTripSerializer(data=request.data)
            if not serializer.is_valid():
                errors = serializer.errors
                if 'branch' in errors:
                    for err in errors['branch']:
                        if 'required' in str(err).lower():
                            return make_response(code=ErrorCode.MISSING_PARAM, msg='缺少必填参数: branch')
                    return make_response(code=ErrorCode.INVALID_BRANCH, msg='支路编号无效，有效值为 1~4')
                return make_response(code=ErrorCode.BAD_REQUEST, msg=f'请求参数错误: {errors}')

            branch = serializer.validated_data['branch']
            operator = serializer.validated_data.get('operator', 'admin')
            reason = serializer.validated_data.get('reason', '人工远程分闸')

            result = ControlService.send_trip(branch, operator, reason)
            return make_response(data=result, msg='分闸指令已发送，断路器正在断开')

        except ValueError as e:
            return make_response(code=ErrorCode.INVALID_BRANCH, msg=str(e))
        except ConnectionError as e:
            error_msg = str(e)
            if '不可用' in error_msg:
                return make_response(code=ErrorCode.MQTT_UNAVAILABLE, msg=error_msg)
            return make_response(code=ErrorCode.PI_OFFLINE, msg='树莓派离线')
        except Exception as e:
            logger.error(f'发送分闸指令失败: {e}', exc_info=True)
            return make_response(code=ErrorCode.SERVER_ERROR, msg=f'服务器内部错误: {str(e)}')


# ============================================================================
# 6. 修改告警阈值
# ============================================================================

class ControlThresholdView(APIView):
    """
    POST /api/control/threshold
    修改告警触发的温度阈值和面积阈值
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = ThresholdUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                errors = serializer.errors
                # 判断是超出范围还是缺少参数
                for field, errs in errors.items():
                    for err in errs:
                        err_str = str(err).lower()
                        if 'required' in err_str:
                            return make_response(code=ErrorCode.MISSING_PARAM, msg=f'缺少必填参数: {field}')
                return make_response(code=ErrorCode.INVALID_THRESHOLD, msg='阈值超出合理范围（温度 30~120℃，面积 1~30%）')

            temperature = serializer.validated_data['temperature']
            area_ratio = serializer.validated_data['area_ratio']

            from .services import ThresholdService
            result = ThresholdService.set_thresholds(temperature, area_ratio)
            return make_response(data=result, msg='阈值修改成功')

        except Exception as e:
            logger.error(f'修改阈值失败: {e}', exc_info=True)
            return make_response(code=ErrorCode.SERVER_ERROR, msg=f'服务器内部错误: {str(e)}')


# ============================================================================
# 7. SSE 实时数据流
# ============================================================================

class DashboardStreamView(APIView):
    """
    GET /api/dashboard/stream
    SSE 事件流，实时推送温度、告警、红外图像

    认证方式：URL 参数 token
    连接地址：/api/dashboard/stream?token=<access_token>
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        # Token 认证
        token = request.query_params.get('token')
        if not token:
            return make_response(code=ErrorCode.MISSING_PARAM, msg='缺少认证参数: token')

        # 验证 JWT Token
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            if user is None or not user.is_active:
                return make_response(code=ErrorCode.BAD_REQUEST, msg='Token 无效或用户已禁用')
        except (InvalidToken, TokenError) as e:
            return make_response(code=ErrorCode.BAD_REQUEST, msg=f'Token 认证失败: {str(e)}')
        except Exception as e:
            return make_response(code=ErrorCode.BAD_REQUEST, msg=f'Token 认证失败: {str(e)}')

        # 生成客户端 ID
        client_id = f'{user.id}-{uuid.uuid4().hex[:8]}'

        # 创建 SSE 流式响应
        response = StreamingHttpResponse(
            self._event_generator(client_id),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Access-Control-Allow-Origin'] = '*'
        response['Connection'] = 'keep-alive'
        return response

    def _event_generator(self, client_id: str):
        """
        SSE 事件生成器
        每个客户端拥有独立的消息队列，从 SSEManager 接收广播消息
        """
        client_queue: queue.Queue = queue.Queue(maxsize=256)
        sse_manager.register(client_id, client_queue)

        try:
            # 发送连接成功事件
            yield self._format_sse('connected', json.dumps({
                'client_id': client_id,
                'message': 'SSE 连接成功',
            }))

            # 发送初始状态数据
            try:
                initial_data = DashboardService.get_realtime_status()
                yield self._format_sse('status', json.dumps(initial_data, ensure_ascii=False))
            except Exception as e:
                logger.error(f'SSE 发送初始状态失败: {e}')

            # 事件循环
            while True:
                try:
                    msg = client_queue.get(timeout=30)
                    yield self._format_sse(msg['event'], msg['data'])
                except queue.Empty:
                    # 发送心跳，保持连接
                    yield self._format_sse('heartbeat', json.dumps({
                        'timestamp': timezone.localtime(timezone.now()).isoformat(),
                    }))

        except GeneratorExit:
            # 客户端断开连接
            pass
        except Exception as e:
            logger.error(f'SSE 事件生成器异常: {e}')
        finally:
            sse_manager.unregister(client_id)

    @staticmethod
    def _format_sse(event: str, data: str) -> str:
        """格式化 SSE 消息"""
        return f'event: {event}\ndata: {data}\n\n'
