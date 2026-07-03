from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.utils import timezone
from .models import Device, DeviceData, DeviceControl
from .serializers import (
    DeviceSerializer, DeviceCreateSerializer,
    DeviceDataSerializer, DeviceDataCreateSerializer,
    DeviceControlSerializer, DeviceControlCreateSerializer
)
from utils.mqtt_client import mqtt_instance
from django.conf import settings


class DeviceListView(generics.ListCreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DeviceCreateSerializer
        return DeviceSerializer


class DeviceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]


class DeviceDataListView(generics.ListCreateAPIView):
    serializer_class = DeviceDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        device_id = self.kwargs.get('device_id')
        queryset = DeviceData.objects.filter(device_id=device_id).order_by('-data_time')
        return queryset
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DeviceDataCreateSerializer
        return DeviceDataSerializer


class DeviceControlListView(generics.ListCreateAPIView):
    serializer_class = DeviceControlSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        device_id = self.kwargs.get('device_id')
        queryset = DeviceControl.objects.filter(device_id=device_id).order_by('-created_at')
        return queryset
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DeviceControlCreateSerializer
        return DeviceControlSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        control_record = serializer.save(
            operator_id=request.user.id,
            status='pending'
        )
        
        mqtt_topic = settings.MQTT_CONFIG['TOPICS']['device_control']
        mqtt_data = {
            'device_id': control_record.device.device_id,
            'control_type': control_record.control_type,
            'control_params': control_record.control_params or {},
            'request_id': control_record.id,
            'timestamp': timezone.now().isoformat()
        }
        
        success = mqtt_instance.publish(mqtt_topic, mqtt_data)
        
        if success:
            control_record.status = 'executed'
            control_record.executed_at = timezone.now()
            control_record.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            control_record.status = 'failed'
            control_record.save()
            return Response(
                {'error': 'MQTT消息发布失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MQTTPublishView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request):
        topic = request.data.get('topic')
        data = request.data.get('data')
        
        if not topic or not data:
            return Response(
                {'error': 'topic 和 data 为必填字段'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = mqtt_instance.publish(topic, data)
        
        if success:
            return Response({'success': True, 'message': '消息发布成功'})
        else:
            return Response(
                {'success': False, 'error': '消息发布失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MQTTStatusView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def retrieve(self, request):
        return Response({
            'connected': mqtt_instance.is_connected(),
            'host': settings.MQTT_CONFIG['HOST'],
            'port': settings.MQTT_CONFIG['PORT'],
            'topics': settings.MQTT_CONFIG['TOPICS']
        })


class DeviceSwitchControlView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, device_id):
        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            return Response(
                {'error': '设备不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        action = request.data.get('action')
        if action not in ['on', 'off']:
            return Response(
                {'error': 'action 必须为 on 或 off'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        control_type = 'switch_on' if action == 'on' else 'switch_off'
        
        control_record = DeviceControl.objects.create(
            device=device,
            control_type=control_type,
            control_params={'action': action},
            operator_id=request.user.id,
            status='pending'
        )
        
        mqtt_topic = settings.MQTT_CONFIG['TOPICS']['device_control']
        mqtt_data = {
            'device_id': device.device_id,
            'control_type': control_type,
            'control_params': {'action': action},
            'request_id': control_record.id,
            'timestamp': timezone.now().isoformat()
        }
        
        success = mqtt_instance.publish(mqtt_topic, mqtt_data)
        
        if success:
            control_record.status = 'executed'
            control_record.executed_at = timezone.now()
            control_record.save()
            
            device.status = 'online' if action == 'on' else 'offline'
            device.last_active = timezone.now()
            device.save()
            
            return Response({
                'success': True,
                'message': f'设备已{action}',
                'device_id': device.device_id,
                'status': device.status
            })
        else:
            control_record.status = 'failed'
            control_record.save()
            return Response(
                {'success': False, 'error': 'MQTT消息发布失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )