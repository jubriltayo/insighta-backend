from django.urls import path
from .views import (
    GithubOAuthInitView,
    GithubCallbackView,
    CLITokenExchangeView,
    TokenRefreshView,
    LogoutView,
    WhoAmIView,
)

urlpatterns = [
    path("github", GithubOAuthInitView.as_view(), name="github-oauth-init"),
    path("github/callback", GithubCallbackView.as_view(), name="github-callback"),
    path("cli/token", CLITokenExchangeView.as_view(), name="cli-token-exchange"),
    path("refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("me", WhoAmIView.as_view(), name="whoami"),
]
