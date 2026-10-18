"""E2E HTTPS (WP-3.6b): aplikasi tetap berfungsi di balik CSP proxy dan cookie Secure.

Dijalankan deployment/tls_check.sh. Env: TLS_BASE_URL, TLS_USER, TLS_PASSWORD."""

import os

from playwright.sync_api import expect, sync_playwright

BASE = os.environ["TLS_BASE_URL"].rstrip("/")
USER = os.environ["TLS_USER"]
PASSWORD = os.environ["TLS_PASSWORD"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    # Sertifikat CA lokal Caddy tidak dikenal peramban uji: abaikan galat sertifikat SAJA.
    page = browser.new_context(ignore_https_errors=True).new_page()
    page.set_default_timeout(15_000)
    problems: list[str] = []
    page.on(
        "console",
        lambda m: problems.append(m.text) if "Content Security Policy" in m.text else None,
    )
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.goto(f"{BASE}/login")
    page.get_by_label("Nama pengguna").fill(USER)
    page.get_by_label("Kata sandi").fill(PASSWORD)
    page.get_by_role("button", name="Masuk").click()
    expect(page.locator("header.topbar")).to_contain_text(USER)
    page.get_by_label("Nama", exact=True).fill("Investigasi uji HTTPS")
    page.get_by_role("button", name="Buat investigasi").click()
    expect(page.get_by_role("heading", name="Investigasi uji HTTPS")).to_be_visible()
    cookies = {c["name"]: c for c in page.context.cookies()}
    assert cookies["sessionid"]["secure"] and cookies["sessionid"]["httpOnly"], cookies["sessionid"]
    assert cookies["csrftoken"]["secure"], cookies["csrftoken"]
    assert not problems, f"CSP/skrip bermasalah: {problems}"
    print("  ok  browser: login dan buat investigasi lewat HTTPS tanpa pelanggaran CSP")
    browser.close()
