from django.urls import path
from .views import UserRegisterView, UserDetailView, UserUpdateView

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='user_register'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('me/update/', UserUpdateView.as_view(), name='user_update'),
]