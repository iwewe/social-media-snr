"""E2E WP-1.9c: inspeksi dari UI sampai bukti, dengan worker Celery sungguhan (AT-01..06, AT-14, AT-18).

Bukan test pytest (sengaja tidak bernama test_*): butuh stack sementara dari deployment/e2e.sh
(database snr_e2e, broker terpisah, worker, dataset sampel dari datasets/sample).
Env: E2E_BASE_URL, E2E_USER, E2E_PASSWORD, E2E_SHOTS (opsional).
"""

import os
from urllib.parse import urlsplit

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ["E2E_BASE_URL"].rstrip("/")
USER = os.environ["E2E_USER"]
PASSWORD = os.environ["E2E_PASSWORD"]
SHOTS = os.environ.get("E2E_SHOTS")
FOUR_ROUNDS = "https://x.com/contoh_redaksi/status/9000000001"
ACCESS_LOSS = "https://x.com/contoh_redaksi/status/9000000002"
WAIT = 30_000  # ms; worker lokal dengan dataset kecil jauh lebih cepat, ini hanya batas atas

steps: list[str] = []


def step(name: str) -> None:
    steps.append(name)
    print(f"  ok  {name}", flush=True)


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def register_target(page: Page, url: str):
    form = page.locator("form:has(h3:has-text('Daftarkan target'))")
    form.get_by_label("Platform").select_option("x")
    form.get_by_label("Jenis target").select_option("post")
    form.get_by_label("URL target").fill(url)
    form.get_by_role("button", name="Daftarkan target").click()
    card = page.locator(f"article[aria-label='Target {url}']")
    expect(card).to_be_visible()
    return card


def newest(card):
    return card.locator("div.run").first


def inspect(card, button: str, expected_runs: int) -> None:
    """Tekan tombol lalu tunggu run baru selesai (final), bukan hanya terkirim."""
    card.get_by_role("button", name=button, exact=True).click()
    expect(card.locator("div.run")).to_have_count(expected_runs, timeout=WAIT)
    final = newest(card).locator("[data-run-status]")
    expect(final).not_to_have_attribute("data-run-status", "PENDING", timeout=WAIT)
    expect(final).not_to_have_attribute("data-run-status", "RUNNING", timeout=WAIT)
    expect(card.get_by_role("button", name="Inspect Again", exact=True)).to_be_enabled(timeout=WAIT)


def badge(card) -> str:
    return card.locator("header .badge.state").first.get_attribute("data-state") or ""


def open_newest_run(page: Page, card) -> None:
    card.get_by_role("link", name="Lihat respons mentah dan bukti").first.click()
    expect(page.get_by_role("heading", name="Respons mentah")).to_be_visible()


def row(page: Page, post_id: str):
    return page.locator(f"table[aria-label='Respons mentah'] tr:has(td:nth-child(2) code:text-is('{post_id}'))")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.set_default_timeout(15_000)

        page.goto(f"{BASE}/login")
        page.get_by_label("Nama pengguna").fill(USER)
        page.get_by_label("Kata sandi").fill(PASSWORD)
        page.get_by_role("button", name="Masuk").click()
        expect(page.locator("header.topbar")).to_contain_text(USER)
        page.get_by_label("Nama", exact=True).fill("E2E inspeksi")
        page.get_by_role("button", name="Buat investigasi").click()
        expect(page.get_by_role("heading", name="E2E inspeksi")).to_be_visible()
        investigation_url = page.url
        step("login dan investigasi dibuat")

        # --- target 1: skenario 4 putaran ---------------------------------------------------
        card = register_target(page, FOUR_ROUNDS)
        expect(card.get_by_text("Konteks target belum diisi")).to_be_visible()
        assert badge(card) == "not_inspected"
        expect(card.get_by_text("Belum pernah diperiksa. Tekan Inspect")).to_be_visible()
        step("target baru: 'Belum diperiksa' dan pemberitahuan konteks belum cukup")

        inspect(card, "Inspect", 1)
        run1 = newest(card)
        expect(run1.locator("[data-run-status]")).to_have_attribute("data-run-status", "COMPLETED")
        assert badge(card) == "has_data"
        expect(run1.locator("[data-field='displayed']")).to_have_text("4")
        expect(run1.locator("[data-field='observed-replies']")).to_have_text("4")
        expect(run1.locator("[data-field='observed-objects']")).to_have_text("5")
        expect(run1.locator(".reconciliation")).to_contain_text("Baru: 5")
        shot(page, "10-run-1")
        step("run 1 selesai: ada data; dua angka terpisah; 5 objek baru")

        inspect(card, "Inspect Again", 2)
        assert newest(card).locator("[data-run-status]").get_attribute("data-run-status") == "COMPLETED"
        expect(newest(card).locator(".reconciliation")).to_contain_text("Baru: 2")
        expect(newest(card).locator(".reconciliation")).to_contain_text("Berubah: 1")
        assert page.locator("article[aria-label^='Target ']").count() == 1  # AT-01: satu target
        step("run 2: objek baru ditambahkan, satu berubah, tanpa target ganda (AT-01/03/05)")

        inspect(card, "Inspect Again", 3)
        run3 = newest(card)
        expect(run3.locator("[data-run-status]")).to_have_attribute("data-run-status", "PARTIAL")
        assert badge(card) == "partial"
        expect(run3.get_by_text("Sebagian balasan tidak termuat")).to_be_visible()
        expect(run3.locator("[data-field='pagination']")).to_have_text("tidak lengkap")
        shot(page, "11-run-3-parsial")
        step("run 3 parsial: 'Data sebagian', paginasi tidak lengkap, pesan jelas")

        # Respons mentah run 3: objek yang tidak muncul ditandai, bukan dihapus (AT-04).
        open_newest_run(page, card)
        missing = row(page, "9000000014")
        expect(missing).to_have_attribute("data-reconciliation", "NOT_OBSERVED")
        expect(missing).to_contain_text("Terakhir terlihat pada run #2")
        expect(missing).to_contain_text("Tidak teramati kali ini")
        # Kolom Perubahan dan Keterangan tidak boleh menyebut penghapusan (isi balasan boleh: itu data).
        status_cells = missing.locator("td").nth(6).inner_text() + missing.locator("td").nth(7).inner_text()
        assert "hapus" not in status_cells.lower(), status_cells
        expect(row(page, "9000000012")).to_contain_text("(diedit")
        # 6 objek teramati pada run ini + 1 objek tidak teramati yang tetap ditampilkan.
        expect(page.get_by_text("Menampilkan 1-7 dari 7 objek")).to_be_visible()
        shot(page, "12-respons-run-3")
        step("respons run 3: objek tidak teramati ditandai dan data terakhir terlihat (AT-04)")

        page.get_by_role("link", name="Kembali ke target").click()
        expect(page.get_by_role("heading", name="E2E inspeksi")).to_be_visible()
        assert page.url == investigation_url
        card = page.locator(f"article[aria-label='Target {FOUR_ROUNDS}']")
        expect(card.locator("div.run")).to_have_count(3)  # riwayat dimuat ulang dari server
        step("tautan kembali ke target; riwayat run dimuat dari server")

        inspect(card, "Inspect Again", 4)
        expect(newest(card).locator("[data-run-status]")).to_have_attribute("data-run-status", "COMPLETED")
        open_newest_run(page, card)
        if SHOTS:  # dipakai tamper_flow untuk membuka halaman bukti run ini
            with open(f"{SHOTS}/run4.url", "w") as handle:
                handle.write(urlsplit(page.url).path)
        gone = row(page, "9000000014")
        expect(gone).to_have_attribute("data-reconciliation", "CONFIRMED_UNAVAILABLE")
        expect(gone).to_contain_text("Bukti dari sumber")
        expect(gone).to_contain_text("dihapus")
        artifacts = page.get_by_role("table", name="Artefak")
        expect(artifacts.locator("tr[data-kind='dom_snapshot']")).to_have_count(1)
        expect(artifacts.locator("tr[data-kind='manifest']")).to_have_count(1)
        hashes = artifacts.locator("code")
        for i in range(hashes.count()):
            assert len(hashes.nth(i).get_attribute("title") or "") == 64  # SHA-256 lengkap
        expect(page.get_by_text("tidak membuktikan keaslian konten platform")).to_be_visible()
        shot(page, "13-bukti-run-4")
        step("run 4: dinyatakan tidak tersedia oleh sumber; artefak DOM + manifest dengan SHA-256 (AT-06)")

        # Verifikasi hash ulang dari disk: berkas belum diubah, jadi semuanya cocok (FR-040).
        page.get_by_role("button", name="Verifikasi semua artefak").click()
        summary = page.locator("[data-run-verification]")
        expect(summary).to_have_attribute("data-run-verification", "ok")
        expect(summary).to_contain_text("2 artefak diperiksa: 2 cocok")
        expect(summary.locator("[data-manifest]")).to_have_attribute("data-manifest", "CONSISTENT")
        expect(artifacts.locator("tr[data-kind='dom_snapshot'] [data-verification='MATCH']")).to_be_visible()
        shot(page, "15-verifikasi-cocok")
        step("verifikasi hash: semua artefak cocok dan manifest konsisten (FR-040)")

        page.set_viewport_size({"width": 390, "height": 800})
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 0, f"scroll horizontal di layar 390px: {overflow}px"
        page.set_viewport_size({"width": 1100, "height": 900})
        step("halaman respons 390px tanpa scroll horizontal (tabel bergulir di wadahnya)")

        page.get_by_role("link", name="Kembali ke target").click()
        card = page.locator(f"article[aria-label='Target {FOUR_ROUNDS}']")
        inspect(card, "Inspect Again", 5)  # dataset hanya punya 4 snapshot
        run5 = newest(card)
        expect(run5.locator("[data-run-status]")).to_have_attribute("data-run-status", "UNSUPPORTED")
        assert badge(card) == "access_failed"
        expect(run5.get_by_role("alert")).to_contain_text("Belum didukung")
        step("run melebihi dataset: 'Belum didukung', keadaan 'Gagal mengakses data'")

        # --- target 2: gangguan akses (AT-14) -----------------------------------------------
        card2 = register_target(page, ACCESS_LOSS)
        inspect(card2, "Inspect", 1)
        assert badge(card2) == "has_data"
        inspect(card2, "Inspect Again", 2)
        run = newest(card2)
        expect(run.locator("[data-run-status]")).to_have_attribute("data-run-status", "ACCESS_RESTRICTED")
        assert badge(card2) == "access_failed"
        expect(card2.locator("header .badge.state").first).to_have_text("Gagal mengakses data")
        expect(run.get_by_role("alert")).to_contain_text("Akses ditolak")
        shot(page, "14-akses-ditolak")
        step("akses ditolak: 'Gagal mengakses data', bukan 'Tidak ada data' (AT-14)")

        open_newest_run(page, card2)
        expect(page.locator("[data-empty]")).to_contain_text("bukan berarti tidak ada balasan")
        assert page.locator("table[aria-label='Respons mentah']").count() == 0
        page.get_by_role("link", name="Kembali ke target").click()
        card2 = page.locator(f"article[aria-label='Target {ACCESS_LOSS}']")

        inspect(card2, "Inspect Again", 3)
        expect(newest(card2).get_by_role("alert")).to_contain_text("Struktur halaman tidak dikenali")
        inspect(card2, "Inspect Again", 4)
        assert badge(card2) == "has_data"
        expect(newest(card2).locator("[data-field='observed-replies']")).to_have_text("2")
        step("parser gagal terlihat jelas; pemulihan pada run berikutnya kembali 'Ada data' (AT-14)")

        # --- kredensial tidak ada di penyimpanan peramban -----------------------------------
        keys = page.evaluate("Object.keys(localStorage).concat(Object.keys(sessionStorage))")
        assert keys == [], f"penyimpanan peramban tidak kosong: {keys}"
        step("tidak ada kredensial di localStorage/sessionStorage")

        browser.close()
    print(f"\nE2E INSPEKSI LULUS: {len(steps)} langkah", flush=True)


if __name__ == "__main__":
    main()
