from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from apps.common.response import Result
from .serializers import LoginSerializer, ChangePasswordSerializer, UserInfoSerializer

User = get_user_model()


def _first_error(errors):
    """提取 serializer.errors 中第一条错误消息"""
    for field, msgs in errors.items():
        for msg in msgs:
            return str(msg), getattr(msg, 'code', None)
    return '参数错误', None


class LoginView(APIView):
    """
    用户登录
    POST /api/auth/login

    请求体：{"username": "...", "password": "..."}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            msg, _ = _first_error(serializer.errors)
            return Result.error(40103, msg)

        username = serializer.validated_data['username'].strip()
        password = serializer.validated_data['password']

        # 40103 — 空值二次校验
        if not username or not password:
            return Result.error(40103, '用户名和密码不能为空')

        # 40102 — 账号禁用检查
        try:
            user = User.objects.get(username=username)
            if not user.is_active:
                return Result.error(40102, '账号已被禁用')
        except User.DoesNotExist:
            pass  # 交给 authenticate 统一处理

        # 40101 — 凭据匹配
        user = authenticate(username=username, password=password)
        if user is None:
            return Result.error(40101, '用户名或密码错误')

        # 生成 JWT
        refresh = RefreshToken.for_user(user)

        return Result.success(
            msg='登录成功',
            data={
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'expires_in': int(jwt_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': 'admin' if user.is_staff else 'operator',
                    'role_display': '管理员' if user.is_staff else '运维人员',
                },
            },
        )


class UserMeView(APIView):
    """
    获取当前用户信息
    GET /api/auth/me

    JWT 认证由 DRF + 全局异常处理器保证，过期/无效 → 40104
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserInfoSerializer(request.user)
        return Result.success(msg='获取成功', data=serializer.data)


class ChangePasswordView(APIView):
    """
    修改密码
    POST /api/auth/change-password

    请求体：{"old_password": "...", "new_password": "..."}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            msg, code = _first_error(serializer.errors)
            # 优先使用序列化器中设置的业务错误码
            if code is not None:
                return Result.error(int(code) if isinstance(code, str) else code, msg)
            return Result.error(40103, msg)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Result.success(msg='密码修改成功，请使用新密码重新登录')
