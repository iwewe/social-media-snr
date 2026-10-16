# Image backend SNR. Target: "app" (web + worker analisis) dan "browser" (worker Playwright).
FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project

# --- app: web dan worker analisis ---
FROM base AS app
# Kode aplikasi di-mount dari host saat pengembangan (lihat compose.yaml).
COPY backend/ ./
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- browser: worker Playwright (menambah Chromium dan dependensi sistemnya) ---
FROM base AS browser
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN uv sync --locked --no-install-project --group browser \
    && playwright install --with-deps chromium \
    && chmod -R a+rX /opt/pw-browsers
COPY backend/ ./
CMD ["celery", "-A", "config", "worker", "-Q", "browser", "-l", "info"]
