"""Taksonomi M2 (PRD 11.2; FR-051..FR-053). Dimensi dipisah; tidak ada skor atau vonis."""

from enum import StrEnum


class IssueStance(StrEnum):
    PRO = "PRO"
    CONTRA = "CONTRA"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"
    UNDETERMINED = "UNDETERMINED"
    NOT_RELEVANT = "NOT_RELEVANT"


class TargetAlignment(StrEnum):
    """Mendukung/menentang posting yang LANGSUNG dibalas, bukan otomatis seed awal."""

    SUPPORT = "SUPPORT"
    OPPOSE = "OPPOSE"
    UNCLEAR = "UNCLEAR"


class Sentiment(StrEnum):
    """Nada emosional bila dapat dinilai; tidak menggantikan stance."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class Character(StrEnum):
    """Karakter respons (multi-label), taksonomi kerja awal RC-01..RC-10."""

    SUPPORT = "RC-01"
    SUBSTANTIVE_CRITICISM = "RC-02"
    COUNTERARGUMENT = "RC-03"
    INFORMATION_REQUEST = "RC-04"
    PERSONAL_ATTACK = "RC-05"
    RIDICULE = "RC-06"
    INTIMIDATION = "RC-07"
    TOPIC_DIVERSION = "RC-08"
    PROMOTIONAL = "RC-09"
    OTHER = "RC-10"


class NarrativeFunction(StrEnum):
    """Fungsi naratif (taksonomi kerja, deskriptif; bukan pembuktian manipulasi)."""

    REINFORCEMENT = "reinforcement"
    EVIDENCE_CONTESTATION = "evidence_contestation"
    COUNTER_FRAMING = "counter_framing"
    SOURCE_DELEGITIMIZATION = "source_delegitimization"
    TOPIC_REDIRECTION = "topic_redirection"
    DISCUSSION_SUPPRESSION = "discussion_suppression"


CHARACTER_NAMES = {
    Character.SUPPORT: "Support / Affirmation",
    Character.SUBSTANTIVE_CRITICISM: "Substantive Criticism",
    Character.COUNTERARGUMENT: "Counterargument",
    Character.INFORMATION_REQUEST: "Information Request",
    Character.PERSONAL_ATTACK: "Personal Attack",
    Character.RIDICULE: "Ridicule / Mockery",
    Character.INTIMIDATION: "Intimidation / Threat (perlu tinjauan manusia)",
    Character.TOPIC_DIVERSION: "Topic Diversion",
    Character.PROMOTIONAL: "Promotional / Spam",
    Character.OTHER: "Other / Unclear",
}
