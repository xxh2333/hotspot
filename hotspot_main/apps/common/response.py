from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework import status


def _get_trace_id(request):
    """从 request 中提取中间件注入的 trace_id"""
    if request and hasattr(request, 'trace_id'):
        return request.trace_id
    return ''


def custom_exception_handler(exc, context):
    """
    自定义 DRF 异常处理器
    将 DRF 默认的认证/权限错误转换为统一响应格式
    """
    request = context.get('request')
    trace_id = _get_trace_id(request)
    response = exception_handler(exc, context)

    if response is not None:
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            return Response(
                {'code': 40104, 'msg': 'Token 无效或已过期', 'data': None, 'success': False, 'trace_id': trace_id},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if response.status_code == status.HTTP_403_FORBIDDEN:
            return Response(
                {'code': 20005, 'msg': '无访问权限', 'data': None, 'success': False, 'trace_id': trace_id},
                status=status.HTTP_403_FORBIDDEN,
            )

    return response


class Result:
    """
    统一响应工具类
    格式：{"code": 0, "msg": "...", "data": {}, "success": true, "trace_id": "..."}
    trace_id 由 TraceIdMiddleware 自动生成，无需手动传入
    """

    @staticmethod
    def success(msg='成功', data=None, request=None):
        return Response({
            'code': 0,
            'msg': msg,
            'data': data,
            'success': True,
            'trace_id': _get_trace_id(request),
        })

    @staticmethod
    def error(code, msg, data=None, request=None):
        return Response({
            'code': code,
            'msg': msg,
            'data': data,
            'success': False,
            'trace_id': _get_trace_id(request),
        })
