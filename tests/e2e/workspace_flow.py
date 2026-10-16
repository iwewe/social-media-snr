"""E2E WP-0.5: alur workspace di browser sungguhan (Playwright).

Bukan test pytest (sengaja tidak bernama test_*): butuh stack hidup dan database terpisah.
Jalankan lewat `make e2e` (deployment/e2e.sh), yang menyiapkan database `snr_e2e` sementara.
Env: E2E_BASE_URL, E2E_USER, E2E_PASSWORD, E2E_SHOTS (folder screenshot, opsional).
"""

import os
import sys

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ["E2E_BASE_URL"].rstrip("/")
USER = os.environ["E2E_USER"]
PASSWORD = os.environ["E2E_PASSWORD"]
SHOTS = os.environ.get("E2E_SHOTS")
NOTE = "Posting menyatakan perusahaan tidak perlu diaudit.\nBaris kedua catatan."
URL_ASLI = "https://twitter.com/u/status/1?s=20"
URL_NORMAL = "https://x.com/u/status/1"

steps: list[str] = []


def step(name: str) -> None:
    steps.append(name)
    print(f"  ok  {name}", flush=True)


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 900})
        page.set_default_timeout(15000)

        # 1. Anonim diarahkan ke login, tidak ada data yang tampil.
        page.goto(f"{BASE}/")
        expect(page.get_by_role("heading", name="Masuk ke SNR")).to_be_visible()
        assert "/login" in page.url
        step("anonim diarahkan ke halaman login")

        page.goto(f"{BASE}/investigations/1")
        expect(page.get_by_role("heading", name="Masuk ke SNR")).to_be_visible()
        step("URL dalam juga diarahkan ke login")

        # 2. Kata sandi salah: pesan jelas, tetap di login.
        page.get_by_label("Nama pengguna").fill(USER)
        page.get_by_label("Kata sandi").fill("salah-sekali")
        page.get_by_role("button", name="Masuk").click()
        expect(page.get_by_role("alert")).to_contain_text("tidak sesuai")
        shot(page, "01-login-gagal")
        step("kata sandi salah ditolak dengan pesan jelas")

        # 3. Login benar.
        page.get_by_label("Kata sandi").fill(PASSWORD)
        page.get_by_role("button", name="Masuk").click()
        expect(page.locator("header.topbar")).to_contain_text(USER)
        # Setelah login, pengguna kembali ke halaman yang semula diminta (/investigations/1).
        # Pada database E2E yang masih kosong halaman itu tidak ada: pesannya harus Indonesia.
        assert page.url.endswith("/investigations/1")
        expect(page.get_by_role("alert")).to_have_text("Data tidak ditemukan.")
        step("login berhasil; kembali ke halaman yang diminta; 404 berbahasa Indonesia")

        page.goto(f"{BASE}/")
        expect(page.get_by_role("heading", name="Investigasi", exact=True)).to_be_visible()
        step("daftar investigasi tampil")

        # 4. Buat investigasi.
        page.get_by_label("Nama", exact=True).fill("E2E Kebakaran hutan")
        page.get_by_role("button", name="Buat investigasi").click()
        expect(page.get_by_role("heading", name="E2E Kebakaran hutan")).to_be_visible()
        step("investigasi dibuat")

        # 5. Petunjuk kontekstual pada form issue.
        issue_form = page.locator("form:has(h3:has-text('Tambah issue'))")
        issue_form.locator("details.help summary").click()
        expect(issue_form.get_by_role("note")).to_contain_text(
            "Bedakan topik isu dari proposition yang dapat diuji"
        )
        shot(page, "02-petunjuk-issue")
        step("petunjuk 'Issue dan proposition' tampil")

        # 6. Issue + proposition.
        issue_form.get_by_label("Judul issue (topik)").fill("Tanggung jawab korporasi")
        issue_form.get_by_role("button", name="Simpan issue").click()
        issue = page.get_by_label("Issue Tanggung jawab korporasi")
        expect(issue).to_be_visible()
        issue.get_by_placeholder("Klaim spesifik yang dapat disetujui atau ditentang").fill(
            "Perusahaan yang diduga terkait kebakaran hutan perlu diaudit"
        )
        issue.get_by_role("button", name="Simpan proposition").click()
        expect(issue.get_by_text("P1", exact=True)).to_be_visible()
        step("issue dan proposition P1 tersimpan")

        # 7. Daftarkan target dengan catatan dan posisi awal.
        target_form = page.locator("form:has(h3:has-text('Daftarkan target'))")
        target_form.get_by_label("Platform").select_option("x")
        target_form.get_by_label("Jenis target").select_option("post")
        target_form.get_by_label("URL target").fill(URL_ASLI)
        target_form.locator("textarea").fill(NOTE)
        target_form.locator("fieldset select").select_option("CONTRA")
        target_form.locator("fieldset details.help summary").click()
        expect(target_form.locator("fieldset").get_by_role("note")).to_contain_text("bukan netral")
        shot(page, "03-form-target")
        target_form.get_by_role("button", name="Daftarkan target").click()

        card = page.locator(f"article[aria-label='Target {URL_NORMAL}']")
        expect(card).to_be_visible()
        expect(card.get_by_role("link", name=URL_NORMAL)).to_be_visible()
        expect(card.get_by_text("Belum diperiksa")).to_be_visible()
        expect(card.get_by_text("P1:")).to_be_visible()
        expect(card.get_by_text("CONTRA", exact=True)).to_be_visible()
        assert card.locator("p.note").first.inner_text() == NOTE
        step("target tersimpan: URL ternormalisasi, 'Belum diperiksa', catatan apa adanya, P1 CONTRA")

        # 7b. Tampilan ponsel: tidak boleh ada scroll horizontal.
        page.set_viewport_size({"width": 390, "height": 800})
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        shot(page, "03b-ponsel")
        assert overflow <= 0, f"scroll horizontal di layar 390px: {overflow}px"
        page.set_viewport_size({"width": 1000, "height": 900})
        step("tampilan 390px tanpa scroll horizontal")

        # 8. Tombol inspeksi belum tersedia, petunjuknya ada.
        expect(card.get_by_role("button", name="Inspect", exact=True)).to_be_disabled()
        expect(card.get_by_role("button", name="Inspect Again")).to_be_disabled()
        card.get_by_label("Petunjuk: Inspeksi ulang").click()
        expect(card.get_by_role("note").filter(has_text="tidak digandakan")).to_be_visible()
        card.get_by_label("Petunjuk: Memulai inspeksi").click()
        expect(card.get_by_role("note").filter(has_text="parsial")).to_be_visible()
        shot(page, "04-kartu-target")
        step("inspeksi dinonaktifkan; petunjuk inspeksi dan inspeksi ulang tampil")

        # 9. URL yang sama (ditulis berbeda) tidak membuat target ganda.
        target_form.get_by_label("URL target").fill("http://www.x.com/u/status/1/")
        target_form.get_by_role("button", name="Daftarkan target").click()
        expect(target_form.get_by_role("alert")).to_contain_text("sudah terdaftar")
        assert page.locator("article[aria-label^='Target ']").count() == 1
        shot(page, "05-target-duplikat")
        step("URL ganda ditolak; tetap satu target (AT-01)")

        # 10. Domain tidak cocok dengan platform.
        target_form.get_by_label("URL target").fill("https://tiktok.com/@u/video/1")
        target_form.get_by_role("button", name="Daftarkan target").click()
        expect(target_form.get_by_role("alert")).to_contain_text("tidak sesuai")
        assert page.locator("article[aria-label^='Target ']").count() == 1
        step("domain tidak sesuai platform ditolak")

        # 11. Revisi catatan menjadi versi 2; versi 1 tetap ada (AT-07).
        card.get_by_role("button", name="Revisi catatan").click()
        card.locator("form textarea").fill("Catatan revisi.")
        card.get_by_role("button", name="Simpan versi baru").click()
        expect(card.get_by_role("heading", name="Catatan konteks (versi 2)")).to_be_visible()
        expect(card.get_by_text("CONTRA", exact=True)).to_be_visible()  # posisi awal dibawa
        card.get_by_role("button", name="Lihat riwayat versi (2)").click()
        history = card.locator("ol")
        expect(history).to_contain_text("Catatan revisi.")
        expect(history).to_contain_text("Posting menyatakan perusahaan tidak perlu diaudit.")
        shot(page, "06-riwayat-versi")
        step("revisi catatan jadi versi 2; versi 1 tetap di riwayat; posisi awal dibawa")

        # 12. Data tetap ada setelah muat ulang (tersimpan di server, bukan di browser).
        page.reload()
        card = page.locator(f"article[aria-label='Target {URL_NORMAL}']")
        expect(card).to_be_visible()
        expect(card.get_by_text("Catatan revisi.").first).to_be_visible()
        step("data bertahan setelah muat ulang")

        # 13. Tidak ada rahasia di penyimpanan browser.
        stored = page.evaluate("JSON.stringify([localStorage, sessionStorage])")
        assert PASSWORD not in stored and "csrftoken" not in stored.lower()
        step("tidak ada kredensial di localStorage/sessionStorage")

        # 14. Logout mengembalikan ke login dan menutup akses.
        page.get_by_role("button", name="Keluar").click()
        expect(page.get_by_role("heading", name="Masuk ke SNR")).to_be_visible()
        page.goto(f"{BASE}/")
        expect(page.get_by_role("heading", name="Masuk ke SNR")).to_be_visible()
        step("logout menutup akses")

        browser.close()
    print(f"\nE2E LULUS: {len(steps)} langkah", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"\nE2E GAGAL setelah {len(steps)} langkah: {exc}", file=sys.stderr, flush=True)
        raise
