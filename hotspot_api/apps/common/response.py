from rest_framework.response import Response


class Result:
    """
    统一响应工具类
    所有接口必须使用它返回数据
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
            'trace_id': trace_id or ''
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
            'trace_id': trace_id or ''
        })