from rest_framework import serializers
from .models import Device, DeviceData, DeviceControl


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id', 'device_id', 'name', 'device_type', 'branch', 'status', 'location', 'ip_address', 'last_active', 'created_at', 'updated_at')


class DeviceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('device_id', 'name', 'device_type', 'branch', 'location', 'ip_address')


class DeviceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceData
        fields = ('id', 'device', 'voltage', 'current', 'power', 'energy', 'temperature', 'humidity', 'power_factor', 'frequency', 'data_time', 'created_at')


class DeviceDataCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceData
        fields = ('device', 'voltage', 'current', 'power', 'energy', 'temperature', 'humidity', 'power_factor', 'frequency', 'data_time')


class DeviceControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceControl
        fields = ('id', 'device', 'control_type', 'status', 'control_params', 'response_data', 'operator_id', 'created_at', 'executed_at')


class DeviceControlCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceControl
        fields = ('device', 'control_type', 'control_params')