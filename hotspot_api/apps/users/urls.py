from django.urls import path
from .views import LoginView, UserMeView, ChangePasswordView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth_login'),
    path('me', UserMeView.as_view(), name='auth_me'),
    path('change-password', ChangePasswordView.as_view(), name='auth_change_password'),
]
