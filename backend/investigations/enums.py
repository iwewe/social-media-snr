from django.db import models


class Platform(models.TextChoices):
    """Lima platform cakupan desain (PRD bagian 7). Identitas dan analisis tidak lintas platform."""

    X = "x", "X"
    THREADS = "threads", "Threads"
    TIKTOK = "tiktok", "TikTok"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"


class TargetType(models.TextChoices):
    POST = "post", "Posting"
    ACCOUNT = "account", "Akun"


class InitialStance(models.TextChoices):
    """Posisi awal target terhadap proposition (FR-013). Bukan label respons (M2)."""

    PRO = "PRO", "PRO"
    CONTRA = "CONTRA", "CONTRA"
    MIXED = "MIXED", "MIXED"
    UNDETERMINED = "UNDETERMINED", "UNDETERMINED"


class Role(models.TextChoices):
    """Peran anggota pada SATU investigasi (ADR 0021). Super admin ditentukan `is_superuser`."""

    OWNER = "OWNER", "Pemilik"
    MEMBER = "MEMBER", "Anggota"
    VIEWER = "VIEWER", "Pembaca"
