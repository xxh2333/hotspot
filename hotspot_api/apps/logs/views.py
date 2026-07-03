from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.common.response import Result
from .services import LogService
from .serializers import OperationLogSerializer, MaintenanceLogSerializer


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
            - operator_name: 操作人姓名（模糊匹配）
        """
        # 调用 Service 获取数据
        data = LogService.get_operation_logs(request, request.user)

        # 序列化结果数据
        serializer = OperationLogSerializer(data['results'], many=True)
        data['results'] = serializer.data

        # 返回统一响应格式
        return Result.success(data=data)


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
        """
        # 调用 Service 获取数据
        data = LogService.get_maintenance_logs(request, request.user)

        # 序列化结果数据
        serializer = MaintenanceLogSerializer(data['results'], many=True)
        data['results'] = serializer.data

        # 返回统一响应格式
        return Result.success(data=data)