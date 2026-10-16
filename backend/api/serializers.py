"""Validasi masukan API. Aturan domain tetap dijaga oleh investigations.services."""

from rest_framework import serializers

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
