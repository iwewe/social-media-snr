import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("snr")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(name="snr.ping")
def ping() -> str:
    """Tugas uji konektivitas worker; dipakai health check dan verifikasi WP-0.2."""
    return "pong"
