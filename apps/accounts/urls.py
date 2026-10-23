from django.urls import path

from apps.accounts.api import user_actions, user_password, users


urlpatterns = [
    path("users/", users),
    path("users/actions/", user_actions),
    path("users/<int:pk>/password/", user_password),
]
