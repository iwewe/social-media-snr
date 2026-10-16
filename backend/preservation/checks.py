"""Django system check untuk konfigurasi jalur penyimpanan (pemisahan evidence vs sesi browser)."""

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, register


@register()
def check_storage_roots(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    evidence = Path(settings.SNR_EVIDENCE_ROOT)
    profiles = Path(settings.SNR_BROWSER_PROFILES_ROOT)
    errors: list[CheckMessage] = []

    for name, root in (("SNR_EVIDENCE_ROOT", evidence), ("SNR_BROWSER_PROFILES_ROOT", profiles)):
        if not root.is_absolute():
            errors.append(Error(f"{name} harus berupa jalur absolut: {root}", id="snr.E001"))

    if errors:
        return errors

    evidence, profiles = evidence.resolve(), profiles.resolve()
    if evidence == profiles or evidence in profiles.parents or profiles in evidence.parents:
        errors.append(
            Error(
                "Akar evidence dan akar sesi browser tidak boleh sama atau bersarang.",
                hint="Sesi browser adalah kredensial; pisahkan dari bukti (PRD bagian 10).",
                id="snr.E002",
            )
        )
    return errors
