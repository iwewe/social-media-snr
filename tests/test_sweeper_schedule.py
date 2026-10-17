"""A1: penjadwalan penyapu run basi: tanpa angka bawaan, gagal keras bila salah konfigurasi."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from collection.tasks import sweep_stale_inspections
from config.sweeper import (
    ENTRY_NAME,
    INTERVAL_VAR,
    OLDER_THAN_VAR,
    TASK_NAME,
    beat_schedule,
    sweep_settings,
)
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

ROOT = Path(__file__).resolve().parents[1]  # akar repo (di kontainer web: "/", file dipasang ke akar)
BACKEND = Path(settings.BASE_DIR)  # backend/ di CI, /app di kontainer


def env(older=None, interval=None) -> dict[str, str]:
    out = {}
    if older is not None:
        out[OLDER_THAN_VAR] = str(older)
    if interval is not None:
        out[INTERVAL_VAR] = str(interval)
    return out


# --- aturan konfigurasi -----------------------------------------------------------------------


def test_nothing_configured_means_no_schedule_and_no_default_number() -> None:
    assert sweep_settings({}, None) is None
    assert beat_schedule({}, None) == {}


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_values_count_as_unset(blank) -> None:
    assert sweep_settings({OLDER_THAN_VAR: blank, INTERVAL_VAR: blank}, None) is None


@pytest.mark.parametrize(("older", "interval", "missing"), [(900, None, INTERVAL_VAR), (None, 60, OLDER_THAN_VAR)])
def test_one_value_alone_is_refused_naming_the_missing_one(older, interval, missing) -> None:
    with pytest.raises(ImproperlyConfigured, match=missing):
        sweep_settings(env(older, interval), None)


@pytest.mark.parametrize("bad", ["abc", "1.5", "-5", "0", "1e3", "٣"])
@pytest.mark.parametrize("which", ["older", "interval"])
def test_invalid_numbers_are_refused(bad, which) -> None:
    values = {OLDER_THAN_VAR: "900", INTERVAL_VAR: "60"}
    values[OLDER_THAN_VAR if which == "older" else INTERVAL_VAR] = bad
    with pytest.raises(ImproperlyConfigured):
        sweep_settings(values, None)


def test_interval_longer_than_the_limit_is_refused_but_equal_is_allowed() -> None:
    with pytest.raises(ImproperlyConfigured, match="tidak boleh lebih besar"):
        sweep_settings(env(60, 61), None)
    assert sweep_settings(env(60, 60), None) == (60, 60)


def test_limit_must_exceed_the_soft_time_limit_or_valid_runs_would_be_swept() -> None:
    with pytest.raises(ImproperlyConfigured, match="SNR_INSPECTION_SOFT_TIME_LIMIT"):
        sweep_settings(env(900, 60), 900)
    with pytest.raises(ImproperlyConfigured):
        sweep_settings(env(600, 60), 900)
    assert sweep_settings(env(901, 60), 900) == (901, 60)
    assert sweep_settings(env(900, 60), None) == (900, 60)


def test_schedule_entry_targets_the_real_task_on_the_analysis_queue() -> None:
    schedule = beat_schedule(env(900, 60), None)
    assert list(schedule) == [ENTRY_NAME]
    entry = schedule[ENTRY_NAME]
    assert entry["task"] == TASK_NAME == sweep_stale_inspections.name
    assert entry["args"] == [900] and entry["schedule"] == 60.0
    assert entry["options"] == {"queue": "analysis"}


def test_the_task_returns_the_swept_run_ids(db) -> None:
    assert sweep_stale_inspections.apply(args=[900]).get() == []


# --- terpasang sungguhan pada settings dan Celery ---------------------------------------------


def run_python(code: str, **extra: str) -> subprocess.CompletedProcess:
    environment = {k: v for k, v in os.environ.items() if not k.startswith("SNR_SWEEP")}
    environment.update(DJANGO_SECRET_KEY="uji", **extra)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=environment,
                          capture_output=True, text=True, timeout=120)


def test_settings_are_disabled_when_the_environment_is_empty() -> None:
    out = run_python("from config import settings; print(settings.CELERY_BEAT_SCHEDULE)")
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "{}"


def test_settings_and_celery_pick_up_the_environment() -> None:
    code = ("import json; from config.celery import app; "
            "print(json.dumps(app.conf.beat_schedule, sort_keys=True))")
    out = run_python(code, SNR_SWEEP_OLDER_THAN_SECONDS="900", SNR_SWEEP_INTERVAL_SECONDS="60")
    assert out.returncode == 0, out.stderr
    entry = json.loads(out.stdout.strip().splitlines()[-1])[ENTRY_NAME]
    assert entry["task"] == TASK_NAME and entry["args"] == [900] and entry["schedule"] == 60.0


@pytest.mark.parametrize("extra", [
    {"SNR_SWEEP_OLDER_THAN_SECONDS": "900"},
    {"SNR_SWEEP_OLDER_THAN_SECONDS": "x", "SNR_SWEEP_INTERVAL_SECONDS": "60"},
    {"SNR_SWEEP_OLDER_THAN_SECONDS": "100", "SNR_SWEEP_INTERVAL_SECONDS": "60",
     "SNR_INSPECTION_SOFT_TIME_LIMIT": "100"},
])
def test_misconfiguration_stops_startup_with_a_clear_message(extra) -> None:
    out = run_python("from config import settings", **extra)
    assert out.returncode != 0
    assert "ImproperlyConfigured" in out.stderr and "SNR_" in out.stderr


# --- compose dan dokumentasi ------------------------------------------------------------------


def test_scheduler_service_runs_beat_without_data_mounts_or_ports() -> None:
    services = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]
    scheduler = services["scheduler"]
    assert "beat" in scheduler["command"] and "ports" not in scheduler
    mounts = " ".join(str(v) for v in scheduler.get("volumes", []))
    assert "evidence" not in mounts and "browser-profiles" not in mounts
    assert "/srv/snr" not in mounts


def test_compose_passes_both_sweeper_variables_with_no_numeric_default() -> None:
    text = (ROOT / "compose.yaml").read_text()
    for var in (OLDER_THAN_VAR, INTERVAL_VAR):
        assert f"{var}: ${{{var}:-}}" in text  # bawaan KOSONG: tidak mengaktifkan apa pun


def test_env_example_documents_the_variables_only_as_comments() -> None:
    lines = (ROOT / ".env.example").read_text().splitlines()
    for var in (OLDER_THAN_VAR, INTERVAL_VAR):
        active = [ln for ln in lines if ln.startswith(var)]
        commented = [ln for ln in lines if ln.startswith(f"# {var}")]
        assert not active and commented, var
