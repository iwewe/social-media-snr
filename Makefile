# Perintah pengembangan SNR. Recipe memakai ">" sebagai prefix agar tidak bergantung pada tab.
.RECIPEPREFIX = >
.DEFAULT_GOAL := help
.PHONY: help install lint typecheck migrations test test-backend test-browser test-frontend t fast mutate fmt ci backend-install frontend-install init-data up down logs ps e2e secrets backup restore-test tls-check demo demo-down

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
> python3 tests/tools/secret_scan.py

typecheck: ## Type-check backend (mypy) dan frontend (tsc)
> cd backend && DJANGO_SECRET_KEY=ci-only-not-a-secret uv run mypy .
> cd frontend && npm run -s typecheck

test-backend: ## Tes backend paralel (pytest-xdist; satu database uji per worker)
> docker compose run --rm -T web pytest -q -n auto --ignore=../tests/browser

test-browser: ## Tes browser (Chromium) di worker-browser; wajib ada Chromium
> docker compose run --rm -T -v ./tests:/tests -e SNR_REQUIRE_BROWSER=1 worker-browser pytest -c pyproject.toml -q ../tests/browser

test-frontend: ## Tes frontend (vitest)
> cd frontend && npm run -s test

test: ## Semua tes SEKALIGUS (backend, browser, frontend berjalan bersamaan)
> $(MAKE) -j3 -Otarget test-backend test-browser test-frontend

t: ## Tingkat 0: tes terarah tanpa xdist. Contoh: make t T="../tests/test_x.py -k nama"
> docker compose run --rm -T web pytest -c pyproject.toml -q -n0 $(T)

mutate: ## Tingkat 2: mutasi sengaja. Contoh: make mutate SPEC=tests/mutation_specs/a3_backend.py
> python3 tests/tools/mutate.py $(SPEC)

fmt: ## Rapikan format kode
> cd backend && uv run ruff check --fix . && uv run ruff format .
> cd frontend && npm run -s format

migrations: ## Pastikan model dan migrasi sinkron (sama seperti langkah CI)
> docker compose run --rm -T web python manage.py makemigrations --check --dry-run

fast: ## Tingkat 0: lint + typecheck + sinkron migrasi bersamaan (tanpa tes); jalankan terus saat menulis kode
> $(MAKE) -j3 -Otarget lint typecheck migrations

ci: fast test ## Tingkat 1: yang dijalankan CI (lint, typecheck, semua tes) sebelum commit/PR
> cd frontend && npm run -s build

init-data: ## Buat direktori data lokal (postgres, evidence, profil browser, backup, ekspor)
> mkdir -p snr-data/data/postgres snr-data/evidence/captures snr-data/evidence/screenshots snr-data/evidence/manifests snr-data/exports snr-data/browser-profiles snr-data/backups snr-data/static snr-data/certs
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

secrets: ## Pindai berkas yang dilacak git untuk cookie/token/kunci (PRD bagian 13)
> python3 tests/tools/secret_scan.py

backup: ## Backup lokal (butuh SNR_BACKUP_DIR di perangkat terpisah); lihat docs/operations.md
> bash deployment/backup.sh

restore-test: ## Uji restore terencana: backup -> restore sementara -> verifikasi -> uji negatif
> bash deployment/restore_test.sh

tls-check: ## Uji HTTPS terisolasi (tumpukan sementara dengan overlay compose.tls.yaml); butuh Docker dan internet
> bash deployment/tls_check.sh

demo: ## Demo web dengan data SINTETIS di database terpisah snr_demo (akun acak di ~/snr-demo/credentials.txt)
> bash deployment/demo.sh up

demo-down: ## Hentikan demo dan hapus database snr_demo
> bash deployment/demo.sh down
