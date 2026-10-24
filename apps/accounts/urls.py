from django.urls import path

from apps.accounts.api import enter_user, user_actions, user_password, users
from apps.accounts.roles_api import role_detail, roles


urlpatterns = [
    path("roles/", roles),
    path("roles/<int:pk>/", role_detail),
    path("users/", users),
    path("users/actions/", user_actions),
    path("users/<int:pk>/enter/", enter_user),
    path("users/<int:pk>/password/", user_password),
]
