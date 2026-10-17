"""Validasi masukan API. Aturan domain tetap dijaga oleh investigations.services."""

from rest_framework import serializers

from collection.contracts import Capability
from investigations.enums import Platform, TargetType


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
