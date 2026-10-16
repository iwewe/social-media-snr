from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("meta/", views.MetaView.as_view(), name="meta"),
    path("investigations/", views.InvestigationListCreateView.as_view(), name="investigations"),
    path("investigations/<int:pk>/", views.InvestigationDetailView.as_view(), name="investigation"),
    path("investigations/<int:pk>/issues/", views.IssueCreateView.as_view(), name="issue-create"),
    path(
        "investigations/<int:pk>/targets/", views.TargetCreateView.as_view(), name="target-create"
    ),
    path(
        "issues/<int:pk>/propositions/",
        views.PropositionCreateView.as_view(),
        name="proposition-create",
    ),
    path(
        "targets/<int:pk>/context-versions/",
        views.TargetContextReviseView.as_view(),
        name="target-context",
    ),
]
