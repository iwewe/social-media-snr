from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path

app_name = "accounts"

urlpatterns = [
    # Satu-satunya halaman aplikasi yang boleh diakses tanpa login.
    path(
        "login/",
        login_not_required(
            auth_views.LoginView.as_view(
                template_name="accounts/login.html", redirect_authenticated_user=True
            )
        ),
        name="login",
    ),
    # LogoutView hanya menerima POST (Django 5).
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
