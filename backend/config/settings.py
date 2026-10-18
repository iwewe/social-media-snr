"""Django settings SNR.

Seluruh konfigurasi sensitif dibaca dari environment variable. Tidak ada rahasia di repo.
"""

import os
from datetime import timedelta
from pathlib import Path

from config.sweeper import beat_schedule

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


DEBUG = _env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"  # noqa: S105 secret-scan: allow (hanya DJANGO_DEBUG=1)
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY wajib diisi (atau set DJANGO_DEBUG=1 untuk dev lokal)."
        )

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "rest_framework",
    # Aplikasi SNR. App reporting sengaja belum ada: desain laporan ditunda (FR-096).
    "accounts",
    "investigations",
    "collection",
    "preservation",
    "intelligence",
    "audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # FR-006: seluruh view wajib login secara default. Pengecualian hanya lewat @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# PostgreSQL adalah satu-satunya basis data yang didukung (PRD bagian 1).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "snr"),
        "USER": os.environ.get("POSTGRES_USER", "snr"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "id"
# Waktu disimpan dalam UTC; published_at/observed_at/captured_at wajib timezone-aware.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery + Valkey (protokol kompatibel Redis).
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TIMEZONE = TIME_ZONE

# Jalur penyimpanan lokal (PRD bagian 10). Evidence dan sesi browser dipisah sejak awal.
SNR_DATA_ROOT = Path(os.environ.get("SNR_DATA_ROOT", "/srv/snr"))
SNR_EVIDENCE_ROOT = SNR_DATA_ROOT / "evidence"
SNR_BROWSER_PROFILES_ROOT = SNR_DATA_ROOT / "browser-profiles"

# Antrean: "browser" hanya diproses worker-browser; "analysis" dan default oleh worker-analysis.
CELERY_TASK_DEFAULT_QUEUE = "analysis"

# --- Autentikasi (FR-001, FR-006) ---
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Pembatasan percobaan login (PRD bagian 13). Angka di bawah adalah nilai awal usulan,
# BELUM disepakati dalam PRD; dapat diubah lewat environment variable.
AXES_FAILURE_LIMIT = int(os.environ.get("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = timedelta(minutes=int(os.environ.get("AXES_COOLOFF_MINUTES", "15")))
# Kunci per kombinasi IP + username: pihak lain tidak bisa mengunci akun dari IP berbeda.
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "api.lockout.lockout_response"

# --- HTTPS di belakang proxy TLS (WP-3.6b). Aktif hanya dengan SNR_HTTPS=1; dev tak berubah ---
# Proxy (deployment/Caddyfile) mengakhiri TLS dan mengirim X-Forwarded-Proto. HSTS: awal usulan
# 1 jam; naikkan bertahap setelah HTTPS terbukti stabil (SNR_HSTS_SECONDS). Tanpa preload/subdomain.
SNR_HTTPS = _env_bool("SNR_HTTPS", False)
if SNR_HTTPS:
    if DEBUG:
        raise RuntimeError("SNR_HTTPS=1 tidak boleh dipakai bersama DJANGO_DEBUG=1.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise RuntimeError("SNR_HTTPS=1 mewajibkan DJANGO_ALLOWED_HOSTS eksplisit (tanpa '*').")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SNR_HSTS_SECONDS", "3600"))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Pengalihan HTTP -> HTTPS dilakukan proxy; di Django tetap dimatikan agar health check internal
    # (HTTP polos dari kontainer) tidak dialihkan.
    SECURE_SSL_REDIRECT = False
    # Sengaja (ADR 0035): pengalihan dilakukan proxy (W008); subdomain dan preload HSTS tidak
    # diaktifkan karena domain deployment belum ditetapkan dan preload hampir tidak dapat dibatalkan
    # (W005, W021).
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]

# --- API untuk frontend (WP-0.5) ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["api.auth.SessionAuth401"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "api.errors.api_exception_handler",
}
# Origin tepercaya tambahan untuk CSRF (mis. frontend dev di port lain), dipisah koma.
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Batas ukuran satu artefak preservasi (byte). Nilai awal usulan; belum ada keputusan di PRD.
SNR_ARTIFACT_MAX_BYTES = int(os.environ.get("SNR_ARTIFACT_MAX_BYTES", str(512 * 1024 * 1024)))

# --- Orkestrasi inspeksi (WP-1.6). PRD tidak menetapkan angka; nilai None = tidak dibatasi dan
# harus ditetapkan setelah pengukuran (pilot I4). Tidak ada angka bawaan yang diklaim final.
SNR_INSPECTION_SOFT_TIME_LIMIT = (
    int(os.environ["SNR_INSPECTION_SOFT_TIME_LIMIT"])
    if os.environ.get("SNR_INSPECTION_SOFT_TIME_LIMIT")
    else None
)
# Penyapu run basi terjadwal (celery beat). Aktif hanya bila DUA nilai ditetapkan eksplisit; tanpa
# angka bawaan (harus diukur: `manage.py inspection_durations`). Salah konfigurasi menghentikan
# startup.
CELERY_BEAT_SCHEDULE = beat_schedule(os.environ, SNR_INSPECTION_SOFT_TIME_LIMIT)
# Adapter yang dimuat saat startup: daftar jalur titik ke kelas tanpa argumen, dipisah koma.
# Direktori dataset uji/impor (WP-1.7). Kosong = adapter dataset tidak terdaftar sama sekali.
SNR_FIXTURE_DATASETS_DIR = (
    Path(os.environ["SNR_FIXTURE_DATASETS_DIR"])
    if os.environ.get("SNR_FIXTURE_DATASETS_DIR")
    else None
)
# Simulasi platform untuk PoC browser (WP-1.8). Kosong = adapter simulasi tidak terdaftar.
SNR_SIMULATION_BASE_URL = os.environ.get("SNR_SIMULATION_BASE_URL") or None
SNR_SIMULATION_PLATFORM = os.environ.get("SNR_SIMULATION_PLATFORM", "x")
SNR_ADAPTERS = [a for a in os.environ.get("SNR_ADAPTERS", "").split(",") if a]
