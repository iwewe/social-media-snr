"""E2E A3b: tim dan peran lintas tiga pengguna (super admin, pemilik, anggota baru).

Bukan test pytest. Dijalankan deployment/e2e.sh setelah flow lain. Env: E2E_BASE_URL, E2E_USER
(pemilik biasa), E2E_ADMIN (super admin), E2E_PASSWORD (sama untuk keduanya), E2E_SHOTS (opsional).
Investigasi dari flow sebelumnya milik E2E_USER (id 1 dan 2) dipakai untuk membuktikan bahwa anggota
baru TIDAK melihatnya.
"""

import os

from playwright.sync_api import Browser, Page, expect, sync_playwright

BASE = os.environ["E2E_BASE_URL"].rstrip("/")
OWNER = os.environ["E2E_USER"]
ADMIN = os.environ["E2E_ADMIN"]
PASSWORD = os.environ["E2E_PASSWORD"]
SHOTS = os.environ.get("E2E_SHOTS")
NEW_USER = "anggota-e2e"
NEW_PASSWORD = "Sandi-anggota-e2e-77-Xq!"

steps: list[str] = []


def step(name: str) -> None:
    steps.append(name)
    print(f"  ok  {name}", flush=True)


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)


def login(browser: Browser, username: str, password: str) -> Page:
    page = browser.new_context(viewport={"width": 1100, "height": 900}).new_page()
    page.set_default_timeout(15_000)
    page.goto(f"{BASE}/login")
    page.get_by_label("Nama pengguna").fill(username)
    page.get_by_label("Kata sandi").fill(password)
    page.get_by_role("button", name="Masuk").click()
    expect(page.locator("header.topbar")).to_contain_text(username)
    return page


def investigation_names(page: Page) -> list[str]:
    page.goto(f"{BASE}/")
    expect(page.get_by_role("heading", name="Investigasi", exact=True)).to_be_visible()
    page.wait_for_load_state("networkidle")
    return page.locator("ul.list li.card a").all_inner_texts()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # 1. Super admin membuat akun anggota (kata sandi lemah ditolak, nama ganda ditolak).
        admin = login(browser, ADMIN, PASSWORD)
        expect(admin.get_by_role("link", name="Akun")).to_be_visible()
        admin.get_by_role("link", name="Akun").click()
        expect(admin.get_by_role("heading", name="Akun", exact=True)).to_be_visible()
        form = admin.get_by_role("form", name="Buat akun")
        form.get_by_label("Nama pengguna").fill(NEW_USER)
        form.get_by_label("Kata sandi awal").fill("123")
        form.get_by_role("button", name="Buat akun").click()
        expect(admin.get_by_role("alert")).to_be_visible()
        assert admin.locator(f"tr[data-account='{NEW_USER}']").count() == 0
        step("super admin: kata sandi lemah ditolak dengan pesan server")

        form.get_by_label("Kata sandi awal").fill(NEW_PASSWORD)
        form.get_by_role("button", name="Buat akun").click()
        expect(admin.get_by_role("status")).to_contain_text(f"Akun {NEW_USER} dibuat")
        row = admin.locator(f"tr[data-account='{NEW_USER}']")
        expect(row).to_contain_text("Aktif")
        expect(row).to_contain_text("belum pernah")
        assert NEW_PASSWORD not in admin.content()
        shot(admin, "30-akun-dibuat")
        step("super admin membuat akun; kata sandi tidak ditampilkan; akun belum pernah masuk")

        form.get_by_label("Nama pengguna").fill(NEW_USER.upper())
        form.get_by_label("Kata sandi awal").fill(NEW_PASSWORD)
        form.get_by_role("button", name="Buat akun").click()
        expect(admin.get_by_role("alert")).to_contain_text("sudah dipakai")
        step("nama pengguna ganda (huruf besar) ditolak")

        # 2. Pemilik membuat investigasi dan menambahkan anggota sebagai Pembaca.
        owner = login(browser, OWNER, PASSWORD)
        owner.get_by_label("Nama", exact=True).fill("Tim E2E")
        owner.get_by_role("button", name="Buat investigasi").click()
        expect(owner.get_by_role("heading", name="Tim E2E")).to_be_visible()
        expect(owner.locator("h1 .badge.role")).to_have_text("Pemilik")
        team_url = owner.url
        issue_form = owner.locator("form:has(h3:has-text('Tambah issue'))")
        issue_form.get_by_label("Judul issue (topik)").fill("Isu tim")
        issue_form.get_by_role("button", name="Simpan issue").click()
        expect(owner.get_by_label("Issue Isu tim")).to_be_visible()
        panel = owner.get_by_role("region", name="Tim")
        expect(panel.locator("tr[data-member='" + OWNER + "']")).to_contain_text("(Anda)")
        step("pemilik: investigasi dibuat, lencana 'Pemilik', dirinya tercantum di tim")

        add = panel.get_by_role("form", name="Tambah anggota")
        add.get_by_label("Nama pengguna").fill("tidak-ada-orang-ini")
        add.get_by_role("button", name="Tambahkan").click()
        expect(panel.get_by_role("alert")).to_contain_text("tidak ditemukan")
        add.get_by_label("Nama pengguna").fill(NEW_USER)
        add.get_by_label("Peran").select_option("VIEWER")
        add.get_by_role("button", name="Tambahkan").click()
        expect(panel.locator(f"tr[data-member='{NEW_USER}']")).to_be_visible()
        expect(panel.get_by_label(f"Peran {NEW_USER}")).to_have_value("VIEWER")
        step("pemilik: pengguna tak dikenal ditolak; anggota ditambahkan sebagai Pembaca")

        panel.get_by_label(f"Peran {OWNER}").select_option("VIEWER")
        expect(panel.get_by_role("alert")).to_contain_text("setidaknya satu OWNER")
        expect(panel.get_by_label(f"Peran {OWNER}")).to_have_value("OWNER")
        step("pemilik terakhir tidak dapat menurunkan dirinya (pesan server; tampilan kembali ke Pemilik)")

        # 3. Anggota baru: hanya melihat investigasi yang diikutinya, hanya-baca.
        member = login(browser, NEW_USER, NEW_PASSWORD)
        names = investigation_names(member)
        assert names == ["Tim E2E"], names
        expect(member.locator("ul.list li.card").first.locator(".badge.role")).to_have_text("Pembaca")
        step("anggota baru: hanya 'Tim E2E' yang terlihat (investigasi pemilik lain tersembunyi), lencana Pembaca")

        member.goto(f"{BASE}/investigations/1")
        expect(member.get_by_role("alert")).to_have_text("Data tidak ditemukan.")
        step("investigasi lain yang ada: 'Data tidak ditemukan.' (identik dengan id yang tidak ada)")

        member.goto(team_url)
        expect(member.get_by_role("heading", name="Tim E2E")).to_be_visible()
        expect(member.locator("[data-readonly]")).to_contain_text("Anda berperan Pembaca")
        expect(member.get_by_label("Issue Isu tim")).to_be_visible()
        assert member.get_by_role("heading", name="Tambah issue").count() == 0
        assert member.get_by_role("form", name="Tambah anggota").count() == 0
        expect(member.get_by_role("region", name="Tim").get_by_text("Hanya Pemilik dan Super admin")).to_be_visible()
        shot(member, "31-pembaca-hanya-baca")
        step("pembaca: data terlihat, formulir tulis dan pengelolaan tim tidak ada")

        # 4. Dipromosikan: berlaku setelah muat ulang.
        panel.get_by_label(f"Peran {NEW_USER}").select_option("MEMBER")
        expect(panel.get_by_label(f"Peran {NEW_USER}")).to_have_value("MEMBER")
        member.reload()
        expect(member.locator("h1 .badge.role")).to_have_text("Anggota")
        form_issue = member.locator("form:has(h3:has-text('Tambah issue'))")
        form_issue.get_by_label("Judul issue (topik)").fill("Dari anggota")
        form_issue.get_by_role("button", name="Simpan issue").click()
        expect(member.get_by_label("Issue Dari anggota")).to_be_visible()
        step("dipromosikan jadi Anggota: formulir muncul dan anggota menulis issue")

        # 5. Dicabut: seketika kehilangan akses.
        panel.get_by_role("button", name=f"Cabut {NEW_USER}").click()
        panel.get_by_role("button", name="Ya").click()
        expect(panel.locator(f"tr[data-member='{NEW_USER}']")).to_have_count(0)
        member.reload()
        expect(member.get_by_role("alert")).to_have_text("Data tidak ditemukan.")
        assert investigation_names(member) == []
        expect(member.get_by_text("Belum ada investigasi yang dapat Anda lihat")).to_be_visible()
        step("dicabut: investigasi hilang dari daftar dan alamat langsung memberi 'Data tidak ditemukan.'")

        # 6. Super admin melihat semuanya dan dapat mengelola tim; pengguna biasa tidak dapat membuka Akun.
        everything = investigation_names(admin)
        assert "Tim E2E" in everything and len(everything) >= 3, everything
        admin.goto(team_url)
        expect(admin.locator("h1 .badge.role")).to_have_text("Super admin")
        expect(admin.get_by_role("form", name="Tambah anggota")).to_be_visible()
        step("super admin: melihat semua investigasi dan dapat mengelola tim")

        owner.goto(f"{BASE}/users")
        expect(owner.get_by_role("alert")).to_contain_text("khusus super admin")
        assert owner.get_by_role("link", name="Akun").count() == 0
        step("pengguna biasa: halaman Akun ditolak dan tautannya tidak ada")

        browser.close()
    print(f"\nE2E TIM LULUS: {len(steps)} langkah", flush=True)


if __name__ == "__main__":
    main()
