from django.urls import path

from .views import LoginView, LogoutView, MeView, PasswordResetView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("password-reset/", PasswordResetView.as_view(), name="auth-password-reset"),
    path("me/", MeView.as_view(), name="auth-me"),
]
