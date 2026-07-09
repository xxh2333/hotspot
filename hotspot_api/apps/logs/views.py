from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.common.response import Result
from .models import OperationLog, MaintenanceLog
from .services import LogService
from .serializers import (
    OperationLogSerializer,
    MaintenanceLogSerializer,
    CreateOperationLogSerializer,
    CreateMaintenanceLogSerializer,
)


class OperationLogListView(APIView):
    """
    人员操作日志列表接口
    GET /api/log/operation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取人员操作日志列表

        Query Parameters:
            - page: 页码，默认1
            - limit: 每页数量，默认10
            - start_time: 开始时间
            - end_time: 结束时间
            - action_type: 操作类型
            - branch: 支路编号
            - user_id: 操作用户ID（精确匹配）
            - maintenance_status: 维护状态（maintained/maintaining/unmaintained）
        """
        data = LogService.get_operation_logs(request, request.user)

        serializer = OperationLogSerializer(data['results'], many=True)
        data['results'] = serializer.data

        return Result.success(data=data, request=request)


class OperationLogCreateView(APIView):
    """
    新增人员操作日志接口
    POST /api/log/operation/create
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        新增人员操作日志

        请求体（JSON）:
            - branch: integer, 必填, 支路编号（1-4）
            - action_type: string, 必填, remote_control/threshold_update/repair_device
            - maintenance_status: string, 必填, maintained/maintaining/unmaintained
            - action_detail: object, 可选, 详情JSON
        """
        serializer = CreateOperationLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Result.error(code=400, msg='参数校验失败', data=serializer.errors, request=request)

        data = LogService.create_operation_log(request, request.user, serializer.validated_data)
        return Result.success(msg='操作日志创建成功', data=data, request=request)


class OperationLogDetailView(APIView):
    """
    人员操作日志详情接口
    GET /api/log/operation/<id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """
        获取单条操作日志详情

        返回字段：id, operator_name, branch, action_type,
                 maintenance_status, maintenance_status_display,
                 action_detail, images, detail, created_at
        """
        log = get_object_or_404(OperationLog, pk=pk)

        # 权限隔离：非管理员只能查看自己的操作日志
        if not request.user.is_superuser and log.user_id != request.user.id:
            return Result.error(code=403, msg='无权限查看该操作日志', request=request)

        serializer = OperationLogSerializer(log)
        return Result.success(data=serializer.data, request=request)


class MaintenanceLogDetailView(APIView):
    """
    故障处置日志详情接口
    GET /api/log/fault/<id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """
        获取单条故障处置日志详情

        返回字段：id, fault_date, fault_time, fault_device,
                 device_code, images, repairer_name,
                 repair_detail, remark
        """
        log = get_object_or_404(MaintenanceLog, pk=pk)

        # 权限隔离：非管理员只能查看自己的维修日志
        if not request.user.is_superuser and log.user_id != request.user.id:
            return Result.error(code=403, msg='无权限查看该处置日志', request=request)

        serializer = MaintenanceLogSerializer(log)
        return Result.success(data=serializer.data, request=request)


class MaintenanceLogListView(APIView):
    """
    故障处置日志列表接口
    GET /api/log/fault
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取故障处置日志列表

        Query Parameters:
            - page: 页码，默认1
            - limit: 每页数量，默认10
            - start_time: 开始时间
            - end_time: 结束时间
            - fault_device: 故障设备类型
            - device_code: 支路编号
            - user_id: 维修人员ID（精确匹配）
        """
        data = LogService.get_maintenance_logs(request, request.user)

        serializer = MaintenanceLogSerializer(data['results'], many=True)
        data['results'] = serializer.data

        return Result.success(data=data, request=request)


class MaintenanceLogCreateView(APIView):
    """
    新增故障处置日志接口
    POST /api/log/fault/create
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        新增故障处置日志

        请求体（JSON）:
            - alarm_id: integer, 必填, 关联告警ID
            - fault_device: string, 可选, 故障设备类型
            - repair_detail: string, 必填, 维修措施描述
            - repair_images: array, 可选, 图片URL数组
            - remark: string, 可选, 备注信息
        """
        serializer = CreateMaintenanceLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Result.error(code=400, msg='参数校验失败', data=serializer.errors, request=request)

        data = LogService.create_maintenance_log(request, request.user, serializer.validated_data)
        return Result.success(msg='处置日志创建成功', data=data, request=request)


class ImageUploadView(APIView):
    """
    通用图片上传接口
    POST /api/log/upload-image
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        上传图片文件

        请求体（multipart/form-data）:
            - image: File, 必填, 图片文件(jpg/png/webp, ≤5MB)
            - type: string, 可选, operation/maintenance（默认 maintenance）
        """
        try:
            data = LogService.upload_image(request, request.user)
            return Result.success(msg='图片上传成功', data=data, request=request)
        except ValueError as e:
            return Result.error(code=400, msg=str(e), request=request)


class LogExportView(APIView):
    """
    日志导出 Excel 接口
    GET /api/log/export/excel
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        导出日志为 Excel 文件

        Query Parameters:
            - log_type: string, 必填, operation/fault
            - start_time: string, 可选, YYYY-MM-DD HH:mm:ss
            - end_time: string, 可选, YYYY-MM-DD HH:mm:ss
        """
        log_type = request.GET.get('log_type')
        if log_type not in ('operation', 'fault'):
            return Result.error(code=400, msg='log_type 必须为 operation 或 fault', request=request)

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')

        try:
            return LogService.export_logs_to_excel(request, request.user, log_type, start_time, end_time)
        except ValueError as e:
            return Result.error(code=400, msg=str(e), request=request)


class LogStatisticsView(APIView):
    """
    日志统计概览接口
    GET /api/log/statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取今日和本月的日志统计数据

        Query Parameters:
            - date: string, 可选, 统计日期 YYYY-MM-DD（默认今天）
        """
        date_str = request.GET.get('date')
        try:
            data = LogService.get_log_statistics(request, request.user, date_str)
            return Result.success(data=data, request=request)
        except ValueError as e:
            return Result.error(code=400, msg=str(e), request=request)