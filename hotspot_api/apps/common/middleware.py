import uuid

from django.utils.deprecation import MiddlewareMixin


class TraceIdMiddleware(MiddlewareMixin):
    """
    TraceId 中间件

    为每个请求生成唯一的 trace_id，用于日志追踪和问题排查。
    - process_request: 注入 request.trace_id
    - process_response: 在响应头 X-Trace-Id 中返回 trace_id
    """

    def process_request(self, request):
        """为每个 HTTP 请求生成唯一追踪 ID"""
        request.trace_id = str(uuid.uuid4())

    def process_response(self, request, response):
        """将 trace_id 写入响应头"""
        if hasattr(request, 'trace_id'):
            response['X-Trace-Id'] = request.trace_id
        return response
