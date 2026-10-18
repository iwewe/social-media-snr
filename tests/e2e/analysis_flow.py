"""E2E WP-2.7b: halaman analisis I2 (respons terklasifikasi, jaringan, profil, temuan).

Bukan test pytest. Dijalankan deployment/e2e.sh setelah analisis dibuat dengan `run_analyses`.
Env: E2E_BASE_URL, E2E_USER, E2E_PASSWORD, E2E_INVESTIGATION (id), E2E_SHOTS (opsional).
"""

import os

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ["E2E_BASE_URL"].rstrip("/")
USER = os.environ["E2E_USER"]
PASSWORD = os.environ["E2E_PASSWORD"]
INVESTIGATION = os.environ["E2E_INVESTIGATION"]
SHOTS = os.environ.get("E2E_SHOTS")
BAD_WORDS = ("skor", "peringkat", "mencurigakan")


def step(name: str) -> None:
    print(f"  ok  {name}", flush=True)


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.set_default_timeout(15_000)
        page.goto(f"{BASE}/login")
        page.get_by_label("Nama pengguna").fill(USER)
        page.get_by_label("Kata sandi").fill(PASSWORD)
        page.get_by_role("button", name="Masuk").click()
        expect(page.locator("header.topbar")).to_contain_text(USER)

        page.goto(f"{BASE}/investigations/{INVESTIGATION}")
        page.get_by_role("link", name=r"Analisis", exact=False).first.click()
        expect(page.get_by_role("heading", name="Analisis:", exact=False)).to_be_visible()
        step("halaman analisis terbuka dari investigasi")

        expect(page.get_by_role("tab", name="Respons")).to_be_visible()
        page.wait_for_load_state("networkidle")
        expect(page.locator("section[aria-label]").first).to_be_visible()
        shot(page, "analysis_responses")
        step("tab respons tampil dengan kategori")

        # Koreksi klasifikasi lewat UI (AT-16); jejaknya diperiksa di tab Jejak audit.
        reason = "Koreksi E2E: konteks percakapan menunjukkan stance berbeda."
        page.get_by_role("button", name="Tinjau", exact=True).first.click()
        form = page.get_by_role("form", name="Tinjau klasifikasi", exact=False)
        for stance in ("Pro", "Kontra", "Campuran"):
            form.locator("select").first.select_option(label=stance)
            form.get_by_label("Alasan peninjauan (wajib)").fill(reason)
            form.get_by_role("button", name="Simpan tinjauan").click()
            try:
                expect(page.get_by_role("form", name="Tinjau klasifikasi", exact=False)).to_have_count(
                    0, timeout=3_000
                )
                break
            except AssertionError:
                continue  # stance sama dengan yang berlaku: server menolak, coba nilai lain
        expect(page.get_by_text("Koreksi E2E", exact=False).first).to_be_visible()
        step("tinjauan klasifikasi disimpan lewat UI")

        page.get_by_role("tab", name="Jaringan").click()
        expect(page.locator(".graph-canvas")).to_be_visible()
        expect(page.get_by_text("Edge interaksi", exact=False).first).to_be_visible()
        shot(page, "analysis_network")
        step("tab jaringan: kanvas dan legenda edge interaksi")

        page.get_by_role("tab", name="Profil akun").click()
        expect(page.locator("p.message[role=note]", has_text="bukan seluruh aktivitas akun").first).to_be_visible()
        step("tab profil: pernyataan cakupan tampil")

        page.get_by_role("tab", name="Temuan").click()
        expect(page.get_by_role("button", name="Buat temuan baru")).to_be_visible()
        page.get_by_role("button", name="Buat temuan baru").click()
        expect(page.get_by_role("form", name="Temuan baru")).to_be_visible()
        assert page.locator("[data-alternative]").count() == 4
        shot(page, "analysis_findings")
        step("tab temuan: formulir dengan empat hipotesis alternatif")

        page.get_by_role("tab", name="Jejak audit").click()
        events = page.locator("li[data-action='CLASSIFICATION_REVIEW']")
        expect(events.first).to_be_visible()
        expect(events.first).to_contain_text(USER)
        expect(events.first).to_contain_text(reason)
        expect(events.first.locator("tr[data-field='issue_stance']")).to_be_visible()
        shot(page, "analysis_audit")
        step("jejak audit: pelaku, alasan, dan sebelum/sesudah tercatat")

        page.get_by_label("Filter jenis perubahan").select_option(label="Konteks target")
        expect(page.locator("li[data-action='TARGET_CONTEXT']").first).to_be_visible()
        expect(page.locator("li[data-action='CLASSIFICATION_REVIEW']")).to_have_count(0)
        step("jejak audit: filter jenis perubahan; pendaftaran target tercatat sebagai konteks target")
        page.get_by_label("Filter jenis perubahan").select_option(label="Semua")
        expect(events.first).to_be_visible()

        events.first.get_by_role("button", name="Buka observasi", exact=False).click()
        drawer = page.get_by_role("dialog", name="Jejak bukti")
        expect(drawer).to_be_visible()
        expect(drawer.get_by_text("Riwayat koreksi klasifikasi")).to_be_visible()
        expect(drawer.locator("li[data-action='CLASSIFICATION_REVIEW']")).to_have_count(1)
        step("satu klik dari jejak ke observasi: laci bukti memuat riwayat koreksinya")
        drawer.get_by_role("button", name="Tutup").click()

        text = (page.locator("main").inner_text()).lower()
        for bad in BAD_WORDS:
            assert bad not in text, f"kata terlarang tampil di UI: {bad}"
        step("tidak ada elemen UI bertema skor/peringkat/kecurigaan")
        browser.close()


main()
