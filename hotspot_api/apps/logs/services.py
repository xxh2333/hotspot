from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from .models import OperationLog, MaintenanceLog, AlarmLog

User = get_user_model()


class LogService:
    """
    日志业务逻辑层
    """

    @staticmethod
    def get_operation_logs(request, user) -> dict:
        """
        获取人员操作日志列表

        Args:
            request: HTTP请求对象
            user: 当前用户对象

        Returns:
            dict: 包含分页数据的字典
        """
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        action_type = request.GET.get('action_type')
        branch = request.GET.get('branch')
        operator_name = request.GET.get('operator_name')

        queryset = OperationLog.objects.all()

        # 权限隔离：非管理员只能查看自己的操作日志
        if not user.is_superuser:
            queryset = queryset.filter(user_id=user.id)

        if start_time:
            queryset = queryset.filter(created_at__gte=start_time)
        if end_time:
            queryset = queryset.filter(created_at__lte=end_time)
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        if branch:
            queryset = queryset.filter(branch=branch)
        if operator_name:
            # 模糊匹配用户名
            user_ids = User.objects.filter(
                username__icontains=operator_name
            ).values_list('id', flat=True)
            queryset = queryset.filter(user_id__in=user_ids)

        queryset = queryset.order_by('-created_at')

        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)

        return {
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': list(page_obj.object_list.values(
                'id', 'user_id', 'branch', 'action_type', 'is_success', 'action_detail', 'created_at'
            ))
        }

    @staticmethod
    def get_maintenance_logs(request, user) -> dict:
        """
        获取故障处置日志列表

        Args:
            request: HTTP请求对象
            user: 当前用户对象

        Returns:
            dict: 包含分页数据的字典
        """
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        fault_device = request.GET.get('fault_device')
        device_code = request.GET.get('device_code')

        queryset = MaintenanceLog.objects.all()

        # 权限隔离：非管理员只能查看自己的维修日志
        if not user.is_superuser:
            queryset = queryset.filter(user_id=user.id)

        if start_time:
            queryset = queryset.filter(created_at__gte=start_time)
        if end_time:
            queryset = queryset.filter(created_at__lte=end_time)
        if fault_device:
            queryset = queryset.filter(fault_device=fault_device)
        if device_code:
            # 通过关联告警的 branch 筛选
            alarm_ids = AlarmLog.objects.filter(branch=device_code).values_list('id', flat=True)
            queryset = queryset.filter(alarm_id__in=alarm_ids)

        queryset = queryset.order_by('-created_at')

        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)

        return {
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': list(page_obj.object_list.values(
                'id', 'alarm_id', 'user_id', 'fault_device', 'repair_detail', 'repair_images', 'created_at'
            ))
        }