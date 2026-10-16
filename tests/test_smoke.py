"""Smoke test WP-0.1: proyek Django dapat dimuat dan app SNR terdaftar."""

from django.apps import apps
from django.conf import settings

SNR_APPS = {"accounts", "investigations", "collection", "preservation", "intelligence"}


def test_snr_apps_are_installed() -> None:
    installed = {cfg.name for cfg in apps.get_app_configs()}
    assert SNR_APPS <= installed


def test_reporting_app_is_not_installed_yet() -> None:
    # FR-096: desain laporan ditunda; reporting hanya placeholder, bukan app aktif.
    assert "reporting" not in settings.INSTALLED_APPS


def test_database_engine_is_postgresql() -> None:
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_evidence_and_browser_profiles_are_separate_roots() -> None:
    evidence = settings.SNR_EVIDENCE_ROOT
    profiles = settings.SNR_BROWSER_PROFILES_ROOT
    assert evidence != profiles
    assert evidence not in profiles.parents
    assert profiles not in evidence.parents
