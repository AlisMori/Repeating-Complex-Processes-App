from django.urls import path
from .views import (
    ActivityView,
    ChangePasswordView,
    DeleteAccountView,
    LoginView,
    MarkShareNotificationsReadView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetView,
    RegisterView,
    ShareNotificationsView,
    SlidingTokenRefreshView,
    UserSearchView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("password-reset/", PasswordResetView.as_view(), name="auth-password-reset"),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("token/refresh/", SlidingTokenRefreshView.as_view(), name="auth-token-refresh"),
    path("activity/", ActivityView.as_view(), name="auth-activity"),
    path("users/search/", UserSearchView.as_view(), name="auth-user-search"),
    path(
        "share-notifications/",
        ShareNotificationsView.as_view(),
        name="auth-share-notifications",
    ),
    path(
        "share-notifications/mark-read/",
        MarkShareNotificationsReadView.as_view(),
        name="auth-share-notifications-mark-read",
    ),
    path("me/", MeView.as_view(), name="auth-me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("delete-account/", DeleteAccountView.as_view(), name="auth-delete-account"),
]
