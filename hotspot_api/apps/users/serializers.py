from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """用户登录序列化器"""
    username = serializers.CharField(
        required=True,
        error_messages={'required': '用户名不能为空', 'blank': '用户名不能为空'},
    )
    password = serializers.CharField(
        required=True,
        error_messages={'required': '密码不能为空', 'blank': '密码不能为空'},
    )


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器"""
    old_password = serializers.CharField(
        required=True,
        error_messages={'required': '旧密码不能为空', 'blank': '旧密码不能为空'},
    )
    new_password = serializers.CharField(
        required=True,
        error_messages={'required': '新密码不能为空', 'blank': '新密码不能为空'},
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('旧密码不正确', code=40106)
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        try:
            validate_password(value, user)
        except DjangoValidationError:
            raise serializers.ValidationError('新密码格式不符合要求', code=40107)
        return value


class UserInfoSerializer(serializers.ModelSerializer):
    """当前用户信息序列化器"""
    role = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'role', 'role_display', 'is_active', 'date_joined', 'last_login')

    def get_role(self, obj):
        return 'admin' if obj.is_staff else 'operator'

    def get_role_display(self, obj):
        return '管理员' if obj.is_staff else '运维人员'
