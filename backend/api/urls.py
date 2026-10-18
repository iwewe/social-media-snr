from django.urls import path

from . import analysis_views as av
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
        "targets/<int:pk>/inspections/",
        views.TargetInspectionsView.as_view(),
        name="target-inspections",
    ),
    path("inspections/<int:pk>/", views.InspectionDetailView.as_view(), name="inspection"),
    path(
        "inspections/<int:pk>/observations/",
        views.InspectionObservationsView.as_view(),
        name="inspection-observations",
    ),
    path(
        "inspections/<int:pk>/acknowledge-review/",
        views.InspectionAcknowledgeView.as_view(),
        name="inspection-acknowledge",
    ),
    path("artifacts/<int:pk>/verify/", views.ArtifactVerifyView.as_view(), name="artifact-verify"),
    path(
        "artifacts/<int:pk>/content/", views.ArtifactContentView.as_view(), name="artifact-content"
    ),
    path(
        "inspections/<int:pk>/verify-artifacts/",
        views.InspectionVerifyArtifactsView.as_view(),
        name="inspection-verify-artifacts",
    ),
    path(
        "investigations/<int:pk>/members/",
        views.InvestigationMembersView.as_view(),
        name="investigation-members",
    ),
    path(
        "investigations/<int:pk>/members/<int:user_id>/role/",
        views.InvestigationMemberRoleView.as_view(),
        name="investigation-member-role",
    ),
    path(
        "investigations/<int:pk>/members/<int:user_id>/revoke/",
        views.InvestigationMemberRevokeView.as_view(),
        name="investigation-member-revoke",
    ),
    path("users/", views.UserListCreateView.as_view(), name="users"),
    path("users/<int:pk>/activation/", views.UserActivationView.as_view(), name="user-activation"),
    path("users/<int:pk>/password/", views.UserPasswordView.as_view(), name="user-password"),
    path(
        "targets/<int:pk>/context-versions/",
        views.TargetContextReviseView.as_view(),
        name="target-context",
    ),
    path(
        "investigations/<int:pk>/analysis-runs/",
        av.AnalysisRunListView.as_view(),
        name="analysis-runs",
    ),
    path("analysis-runs/<int:pk>/", av.AnalysisRunDetailView.as_view(), name="analysis-run"),
    path(
        "analysis-runs/<int:pk>/responses/",
        av.AnalysisResponsesView.as_view(),
        name="analysis-responses",
    ),
    path(
        "assessments/<int:pk>/review/", av.AssessmentReviewView.as_view(), name="assessment-review"
    ),
    path(
        "assessments/<int:pk>/history/",
        av.AssessmentHistoryView.as_view(),
        name="assessment-history",
    ),
    path("analysis-runs/<int:pk>/graph/", av.AnalysisGraphView.as_view(), name="analysis-graph"),
    path(
        "analysis-runs/<int:pk>/coordination/",
        av.AnalysisCoordinationView.as_view(),
        name="analysis-coordination",
    ),
    path(
        "analysis-runs/<int:pk>/profiles/",
        av.AnalysisProfilesView.as_view(),
        name="analysis-profiles",
    ),
    path("profiles/<int:pk>/", av.ProfileDetailView.as_view(), name="profile"),
    path("investigations/<int:pk>/findings/", av.FindingListCreateView.as_view(), name="findings"),
    path(
        "investigations/<int:pk>/findings/evidence/",
        av.FindingEvidenceView.as_view(),
        name="finding-evidence",
    ),
    path("findings/<int:pk>/", av.FindingDetailView.as_view(), name="finding"),
    path("findings/<int:pk>/revise/", av.FindingReviseView.as_view(), name="finding-revise"),
    path("findings/<int:pk>/endorse/", av.FindingEndorseView.as_view(), name="finding-endorse"),
    path("findings/<int:pk>/withdraw/", av.FindingWithdrawView.as_view(), name="finding-withdraw"),
    path("observations/<int:pk>/", av.ObservationDetailView.as_view(), name="observation"),
]
