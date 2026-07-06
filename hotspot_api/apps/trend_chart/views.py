import json
import time
from datetime import datetime

from django.http import StreamingHttpResponse, JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.response import Result
from .services import TrendChartService


def trend_chart_realtime(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return JsonResponse({'code': 401, 'msg': '未授权', 'success': False}, status=401)

    from rest_framework_simplejwt.tokens import AccessToken
    try:
        token = AccessToken(auth_header.split(' ')[1])
    except Exception:
        return JsonResponse({'code': 401, 'msg': 'Token无效', 'success': False}, status=401)

    branch = request.GET.get('branch')
    duration = min(int(request.GET.get('duration', 600)), 3600)

    if branch is not None:
        try:
            branch = int(branch)
            if branch < 1 or branch > 4:
                return JsonResponse({'code': 10001, 'msg': '支路编号无效，应为 1~4', 'success': False}, status=400)
        except (TypeError, ValueError):
            return JsonResponse({'code': 10001, 'msg': '支路编号无效', 'success': False}, status=400)

    def event_stream():
        init_data = TrendChartService.get_recent_logs(branch, duration)
        yield f"event: init\ndata: {json.dumps(init_data, ensure_ascii=False)}\n\n"

        last_heartbeat = time.time()
        last_update = time.time()

        while True:
            current = time.time()

            if current - last_heartbeat >= 30:
                yield f"event: heartbeat\ndata: \"ping\"\n\n"
                last_heartbeat = current

            if current - last_update >= 5:
                latest = TrendChartService.get_latest_log(branch)
                if latest:
                    yield f"event: update\ndata: {json.dumps(latest, ensure_ascii=False)}\n\n"
                last_update = current

            time.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response


class TrendChartHistoryView(APIView):
    """GET /api/trend-chart/history"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branch = request.GET.get('branch')
        range_value = request.GET.get('range')
        start_time_str = request.GET.get('start_time')
        end_time_str = request.GET.get('end_time')

        if not branch or not range_value:
            return Result.error(10002, '缺少必填参数：branch 和 range 为必填', request=request)

        try:
            branch = int(branch)
            if branch < 1 or branch > 4:
                return Result.error(10001, '支路编号无效，应为 1~4', request=request)
        except (TypeError, ValueError):
            return Result.error(10001, '支路编号无效', request=request)

        if range_value not in ('1h', '24h', '7d', '30d'):
            return Result.error(10001, 'range 参数无效，可选值：1h / 24h / 7d / 30d', request=request)

        start_time = None
        end_time = None
        if start_time_str and end_time_str:
            try:
                start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return Result.error(10001, '时间格式无效，请使用 YYYY-MM-DD HH:MM:SS', request=request)

        data = TrendChartService.get_history(branch, range_value, start_time, end_time)
        if data is None:
            return Result.error(30001, '查询时间范围内无数据', request=request)

        return Result.success(data=data, request=request)


class TrendChartThresholdView(APIView):
    """GET /api/trend-chart/threshold"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = TrendChartService.get_threshold()
        return Result.success(data=data, request=request)


class TrendChartAlarmHistoryView(APIView):
    """GET /api/trend-chart/alarm-history"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branch = request.GET.get('branch')
        range_value = request.GET.get('range')
        start_time_str = request.GET.get('start_time')
        end_time_str = request.GET.get('end_time')

        if not branch or not range_value:
            return Result.error(10002, '缺少必填参数：branch 和 range 为必填', request=request)

        try:
            branch = int(branch)
            if branch < 1 or branch > 4:
                return Result.error(10001, '支路编号无效，应为 1~4', request=request)
        except (TypeError, ValueError):
            return Result.error(10001, '支路编号无效', request=request)

        if range_value not in ('1h', '24h', '7d', '30d'):
            return Result.error(10001, 'range 参数无效，可选值：1h / 24h / 7d / 30d', request=request)

        start_time = None
        end_time = None
        if start_time_str and end_time_str:
            try:
                start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return Result.error(10001, '时间格式无效，请使用 YYYY-MM-DD HH:MM:SS', request=request)

        data = TrendChartService.get_alarm_history(branch, range_value, start_time, end_time)
        if data is None:
            return Result.error(30001, '查询时间范围内无告警数据', request=request)

        return Result.success(data=data, request=request)
