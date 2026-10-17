# Perintah pengembangan SNR. Recipe memakai ">" sebagai prefix agar tidak bergantung pada tab.
.RECIPEPREFIX = >
.DEFAULT_GOAL := help
.PHONY: help install lint typecheck test fmt ci backend-install frontend-install init-data up down logs ps e2e

help: ## Tampilkan daftar perintah
> @grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install: backend-install frontend-install ## Pasang seluruh dependensi

backend-install: ## Pasang dependensi backend (uv, Python 3.13)
> cd backend && uv sync --locked

frontend-install: ## Pasang dependensi frontend (npm ci)
> cd frontend && npm ci

lint: ## Lint backend (ruff) dan frontend (oxlint), cek format
> cd backend && uv run ruff check . && uv run ruff format --check .
> cd frontend && npm run -s lint && npm run -s format:check

typecheck: ## Type-check backend (mypy) dan frontend (tsc)
> cd backend && DJANGO_SECRET_KEY=ci-only-not-a-secret uv run mypy .
> cd frontend && npm run -s typecheck

test: ## Test backend (pytest di container web; tes browser di worker-browser) dan frontend (vitest)
> docker compose run --rm -T web pytest -q --ignore=../tests/browser
> docker compose run --rm -T -v ./tests:/tests -e SNR_REQUIRE_BROWSER=1 worker-browser pytest -c pyproject.toml -q ../tests/browser
> cd frontend && npm run -s test

fmt: ## Rapikan format kode
> cd backend && uv run ruff check --fix . && uv run ruff format .
> cd frontend && npm run -s format

ci: lint typecheck test ## Urutan yang sama dengan CI
> cd frontend && npm run -s build

init-data: ## Buat direktori data lokal (postgres, evidence, profil browser, backup, ekspor)
> mkdir -p snr-data/data/postgres snr-data/evidence/captures snr-data/evidence/screenshots snr-data/evidence/manifests snr-data/exports snr-data/browser-profiles snr-data/backups
> chmod 700 snr-data/browser-profiles snr-data/data/postgres

up: init-data ## Jalankan seluruh lingkungan (butuh .env)
> docker compose up -d --build

down: ## Hentikan lingkungan (data tetap ada)
> docker compose down

logs: ## Ikuti log seluruh layanan
> docker compose logs -f --tail=100

ps: ## Status layanan
> docker compose ps

e2e: ## E2E browser (Playwright) pada database terpisah; butuh stack hidup (make up)
> bash deployment/e2e.sh
