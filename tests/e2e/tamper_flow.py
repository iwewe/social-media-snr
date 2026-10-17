"""E2E WP-1.10: berkas bukti yang diubah di disk terdeteksi dan tidak disajikan (FR-040, NFR-02).

Dijalankan setelah inspection_flow oleh deployment/e2e.sh, yang mengubah berkas DOM run 4 di
direktori data sementara. Env: E2E_BASE_URL, E2E_USER, E2E_PASSWORD, E2E_SHOTS (berisi run4.url).
"""

import os
import re

from playwright.sync_api import expect, sync_playwright

BASE = os.environ["E2E_BASE_URL"].rstrip("/")
USER = os.environ["E2E_USER"]
PASSWORD = os.environ["E2E_PASSWORD"]
SHOTS = os.environ["E2E_SHOTS"]
VERIFY = re.compile(r"^Verifikasi artefak")
DOWNLOAD = re.compile(r"^Unduh artefak")

steps: list[str] = []


def step(name: str) -> None:
    steps.append(name)
    print(f"  ok  {name}", flush=True)


def main() -> None:
    run_path = open(f"{SHOTS}/run4.url").read().strip()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900}, accept_downloads=True)
        page.set_default_timeout(15_000)
        downloads: list[object] = []
        page.on("download", lambda d: downloads.append(d))

        page.goto(f"{BASE}/login")
        page.get_by_label("Nama pengguna").fill(USER)
        page.get_by_label("Kata sandi").fill(PASSWORD)
        page.get_by_role("button", name="Masuk").click()
        expect(page.locator("header.topbar")).to_contain_text(USER)
        page.goto(f"{BASE}{run_path}")
        expect(page.get_by_role("table", name="Artefak")).to_be_visible()
        step("halaman bukti run 4 terbuka")

        dom_row = page.locator("tr[data-kind='dom_snapshot']")
        manifest_row = page.locator("tr[data-kind='manifest']")

        dom_row.get_by_role("button", name=VERIFY).click()
        result = dom_row.locator("[data-verification]")
        expect(result).to_have_attribute("data-verification", "MISMATCH")
        expect(result).to_contain_text("tidak boleh dipakai sebagai bukti")
        assert result.get_attribute("role") == "alert"
        page.screenshot(path=f"{SHOTS}/20-berkas-diubah.png", full_page=True)
        step("berkas DOM yang diubah terdeteksi: 'Berbeda dari saat disimpan'")

        manifest_row.get_by_role("button", name=VERIFY).click()
        expect(manifest_row.locator("[data-verification]")).to_have_attribute(
            "data-verification", "MATCH"
        )
        step("artefak lain yang tidak diubah tetap 'Cocok'")

        page.get_by_role("button", name="Verifikasi semua artefak").click()
        summary = page.locator("[data-run-verification]")
        expect(summary).to_have_attribute("data-run-verification", "problem")
        expect(summary).to_contain_text("1 cocok")
        expect(summary).to_contain_text("1 berbeda dari saat disimpan")
        expect(summary.locator("[data-manifest]")).to_have_attribute("data-manifest", "CONSISTENT")
        step("verifikasi semua: ringkasan masalah; manifest tetap konsisten dengan basis data")

        dom_row.get_by_role("button", name=DOWNLOAD).click()
        expect(dom_row.locator("[data-verification]")).to_have_attribute(
            "data-verification", "MISMATCH"
        )
        page.wait_for_timeout(500)
        assert downloads == [], "berkas yang diubah tidak boleh terunduh"
        response = page.request.get(f"{BASE}/api/artifacts/{_artifact_id(dom_row)}/content/")
        assert response.status == 409, response.status
        assert response.json()["code"] == "artifact_integrity_failed"
        step("unduhan berkas yang diubah ditolak (UI tidak mengunduh; server menjawab 409)")

        browser.close()
    print(f"\nE2E BUKTI LULUS: {len(steps)} langkah", flush=True)


def _artifact_id(row) -> int:
    label = row.get_by_role("button", name=VERIFY).get_attribute("aria-label") or ""
    return int(label.rsplit("#", 1)[1])


if __name__ == "__main__":
    main()
