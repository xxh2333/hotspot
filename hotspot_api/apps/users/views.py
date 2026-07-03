from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from apps.common.response import Result
from .serializers import LoginSerializer, ChangePasswordSerializer, UserInfoSerializer

User = get_user_model()


def _first_error(errors):
    for field, msgs in errors.items():
        for msg in msgs:
            return str(msg), getattr(msg, 'code', None)
    return '参数错误', None


class LoginView(APIView):
    """POST /api/auth/login"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            msg, _ = _first_error(serializer.errors)
            return Result.error(40103, msg, request=request)

        username = serializer.validated_data['username'].strip()
        password = serializer.validated_data['password']

        if not username or not password:
            return Result.error(40103, '用户名和密码不能为空', request=request)

        try:
            user = User.objects.get(username=username)
            if not user.is_active:
                return Result.error(40102, '账号已被禁用', request=request)
        except User.DoesNotExist:
            pass

        user = authenticate(username=username, password=password)
        if user is None:
            return Result.error(40101, '用户名或密码错误', request=request)

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
            request=request,
        )


class UserMeView(APIView):
    """GET /api/auth/me"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserInfoSerializer(request.user)
        return Result.success(msg='获取成功', data=serializer.data, request=request)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            msg, code = _first_error(serializer.errors)
            if code is not None:
                return Result.error(int(code) if isinstance(code, str) else code, msg, request=request)
            return Result.error(40103, msg, request=request)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Result.success(msg='密码修改成功，请使用新密码重新登录', request=request)
