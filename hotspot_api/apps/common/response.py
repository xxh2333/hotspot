from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    自定义 DRF 异常处理器
    将 DRF 默认的认证/权限错误转换为统一响应格式
    """
    response = exception_handler(exc, context)

    if response is not None:
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            detail = response.data.get('detail', '')
            if 'Authentication' in str(detail) or 'token' in str(detail).lower():
                return Response(
                    {
                        'code': 40104,
                        'msg': 'Token 无效或已过期',
                        'data': None,
                        'success': False,
                        'trace_id': '',
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {
                    'code': 40104,
                    'msg': '未登录或Token无效',
                    'data': None,
                    'success': False,
                    'trace_id': '',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if response.status_code == status.HTTP_403_FORBIDDEN:
            return Response(
                {
                    'code': 20005,
                    'msg': '无访问权限',
                    'data': None,
                    'success': False,
                    'trace_id': '',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    return response


class Result:
    """
    统一响应工具类
    所有接口必须使用它返回数据
    格式：{"code": 0, "msg": "...", "data": {}, "success": true, "trace_id": "..."}
    """

    @staticmethod
    def success(msg='成功', data=None, trace_id=None):
        """
        成功响应

        Args:
            msg: 响应消息，默认为'成功'
            data: 响应数据
            trace_id: 追踪ID

        Returns:
            Response: Django REST Framework Response 对象
        """
        return Response({
            'code': 0,
            'msg': msg,
            'data': data,
            'success': True,
            'trace_id': trace_id or '',
        })

    @staticmethod
    def error(code, msg, data=None, trace_id=None):
        """
        错误响应

        Args:
            code: 错误代码
            msg: 错误消息
            data: 响应数据（可选）
            trace_id: 追踪ID

        Returns:
            Response: Django REST Framework Response 对象
        """
        return Response({
            'code': code,
            'msg': msg,
            'data': data,
            'success': False,
            'trace_id': trace_id or '',
        })