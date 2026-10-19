"""Validasi masukan API. Aturan domain tetap dijaga oleh investigations.services."""

from typing import Any

from rest_framework import serializers

from audit.models import AuditAction, SubjectType
from collection.contracts import Capability
from intelligence.launch import METHODS
from investigations.enums import Platform, Role, TargetType


class InvestigationInput(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, required=False, default="")


class IssueInput(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    definition = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False
    )


class PropositionInput(serializers.Serializer):
    statement = serializers.CharField()


class StanceInput(serializers.Serializer):
    proposition = serializers.IntegerField()
    stance = serializers.CharField()


class TargetInput(serializers.Serializer):
    platform = serializers.ChoiceField(choices=Platform.choices)
    target_type = serializers.ChoiceField(choices=TargetType.choices)
    url = serializers.CharField(max_length=2000)
    # trim_whitespace=False: catatan disimpan apa adanya (FR-016).
    note = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False
    )
    stances = StanceInput(many=True, required=False)


class ContextRevisionInput(serializers.Serializer):
    note = serializers.CharField(allow_blank=True, trim_whitespace=False)
    # Dihilangkan = bawa stance versi sebelumnya; [] = sengaja tanpa stance.
    stances = StanceInput(many=True, required=False)


class InspectionInput(serializers.Serializer):
    # Dihilangkan = cakupan bawaan untuk jenis target (mis. post + balasan).
    requested = serializers.ListField(
        child=serializers.ChoiceField(choices=[c.value for c in Capability]),
        required=False,
        allow_empty=False,
    )

    def validate_requested(self, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Kemampuan yang diminta tidak boleh ganda.")
        return value


class AcknowledgeInput(serializers.Serializer):
    note = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False, max_length=2000
    )


class PageInput(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=200, required=False, default=50)


class MemberInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=Role.choices)


class RoleInput(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class UserCreateInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class PasswordInput(serializers.Serializer):
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class ActivationInput(serializers.Serializer):
    active = serializers.BooleanField()


class ResponseListInput(PageInput):
    proposition = serializers.IntegerField(required=False)
    stance = serializers.ChoiceField(
        choices=["PRO", "CONTRA", "MIXED", "NEUTRAL", "UNDETERMINED", "NOT_RELEVANT"],
        required=False,
    )
    alignment = serializers.ChoiceField(choices=["SUPPORT", "OPPOSE", "UNCLEAR"], required=False)
    character = serializers.RegexField(r"^RC-(0[1-9]|10)$", required=False)
    origin = serializers.ChoiceField(choices=["machine", "human"], required=False)
    # allow_null: parameter tak ada = tidak memfilter (BooleanField biasa menjadi False)
    needs_review = serializers.BooleanField(required=False, allow_null=True)
    actor = serializers.IntegerField(required=False)


class AssessmentReviewInput(serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True)
    issue_stance = serializers.CharField(required=False)
    target_alignment = serializers.CharField(required=False)
    expression_sentiment = serializers.CharField(required=False, allow_null=True)
    response_character = serializers.ListField(child=serializers.CharField(), required=False)
    narrative_function = serializers.CharField(required=False, allow_null=True)


class GraphInput(serializers.Serializer):
    relation_types = serializers.CharField(required=False)  # dipisah koma
    since = serializers.DateTimeField(required=False)
    until = serializers.DateTimeField(required=False)
    stance = serializers.ChoiceField(
        choices=["PRO", "CONTRA", "MIXED", "UNDETERMINED"], required=False
    )
    max_nodes = serializers.IntegerField(min_value=1, max_value=2000, required=False, default=300)
    include_unknown_time = serializers.BooleanField(required=False, allow_null=True)


class CoordinationInput(PageInput):
    indicator = serializers.RegexField(r"^CO-0[1-6]$", required=False)
    beyond_baseline = serializers.BooleanField(required=False, allow_null=True)
    min_support = serializers.IntegerField(min_value=1, required=False)
    actor = serializers.IntegerField(required=False)


class FindingInput(serializers.Serializer):
    analysis_run_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    indicator_edge_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    observation_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    title = serializers.CharField(max_length=200)
    statement = serializers.CharField(trim_whitespace=False)
    interpretation = serializers.CharField(trim_whitespace=False)
    evidence_ratings = serializers.DictField()
    alternatives = serializers.DictField(required=False, default=dict)
    confidence = serializers.CharField()
    confidence_reason = serializers.CharField(trim_whitespace=False)


class FindingNoteInput(serializers.Serializer):
    note = serializers.CharField(trim_whitespace=True)


class AuditListInput(PageInput):
    action = serializers.ChoiceField(choices=AuditAction.choices, required=False)
    subject_type = serializers.ChoiceField(choices=SubjectType.choices, required=False)
    subject_id = serializers.IntegerField(min_value=1, required=False)
    actor = serializers.CharField(max_length=150, required=False)
    observation = serializers.IntegerField(min_value=1, required=False)


class EvidenceAccessInput(PageInput):
    purpose = serializers.ChoiceField(choices=["verify", "verify_run", "download"], required=False)
    result = serializers.ChoiceField(
        choices=["MATCH", "MISMATCH", "MISSING", "UNREADABLE"], required=False
    )
    user = serializers.CharField(max_length=150, required=False)
    artifact = serializers.IntegerField(min_value=1, required=False)


class DatasetCreateInput(serializers.Serializer):
    inspection_run_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=500
    )
    note = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")


class AnalysisRunCreateInput(serializers.Serializer):
    method = serializers.ChoiceField(choices=list(METHODS))
    dataset_id = serializers.IntegerField(min_value=1)
    proposition_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    source_run_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    parameters = serializers.DictField()
    # Versi konteks yang dibekukan: kosong = terbaru. Kunci target = id target (teks angka).
    issue_context_version = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    target_context_versions = serializers.DictField(
        child=serializers.IntegerField(min_value=1, allow_null=True), required=False, default=dict
    )

    def validate_target_context_versions(self, value: dict[str, Any]) -> dict[int, int | None]:
        try:
            return {int(k): v for k, v in value.items()}
        except ValueError:
            raise serializers.ValidationError("kunci harus id target (angka)") from None


class ReanalyzeInput(serializers.Serializer):
    use_latest_context = serializers.BooleanField(required=False, default=False)
