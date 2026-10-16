"""WP-1.5b: penyaring rahasia (PRD bagian 10 dan 13). Semua 'rahasia' di sini PALSU dan disusun saat
runtime dari potongan kecil, agar repositori tidak memuat pola kredensial utuh (pemindai rahasia
GitHub dan hook detect-private-key kita sendiri akan menandainya)."""

import logging
import time

import pytest
from collection.contracts import ArtifactCapture, ArtifactKind
from preservation.policy import PolicyDecision
from preservation.secret_filter import (
    OVERLAP,
    SecretFilterPolicy,
    filename_finding,
    is_secret_filename,
    scan_bytes,
)

POLICY = SecretFilterPolicy()

# --- 'rahasia' palsu yang disusun saat runtime ----------------------------------------------------
JWT = ".".join(["eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiJ1c2VyMTIzIn0", "c2lnbmF0dXJl" + "MTIzNDU2"])
PEM = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
GH = "gh" + "p_" + "a" * 36
SLACK = "xo" + "xb-" + "1234567890-abcdefghij"
GOOGLE = "AI" + "za" + "S" * 35
STRIPE = "sk_" + "live_" + "a1b2c3d4e5f6g7h8"
SESSION_VALUE = "a1b2c3d4e5f6g7h8i9"


def dom(text: str | bytes, name="halaman.html", ctype="text/html", note=None) -> ArtifactCapture:
    data = text.encode() if isinstance(text, str) else text
    return ArtifactCapture(ArtifactKind.DOM_SNAPSHOT, name, data, ctype, note=note)


def decide(capture: ArtifactCapture) -> PolicyDecision:
    return POLICY.check(capture)


# =============================== nama berkas ===============================


@pytest.mark.parametrize(
    ("name", "rule"),
    [
        ("cookies.txt", "name:cookies"),
        ("Cookies", "name:cookies"),
        ("cookies-export.json", "name:cookies"),
        ("cookies.sqlite", "name:cookies"),
        ("storage_state.json", "name:storage-state"),
        ("Storage-State-x.json", "name:storage-state"),
        ("sesi.har", "name:har"),
        ("SESI.HAR", "name:har"),
        ("server.pem", "name:key-material"),
        ("tls.key", "name:key-material"),
        ("bundle.p12", "name:key-material"),
        ("id_rsa", "name:key-material"),
        ("id_ed25519.pub", "name:key-material"),
        (".env", "name:env-file"),
        (".env.production", "name:env-file"),
        ("passwords.txt", "name:secret-name"),
        ("credentials.json", "name:secret-name"),
        ("secret", "name:secret-name"),
        ("api-credentials.yaml", "name:secret-name"),
        ("access.token.json", "name:secret-name"),
        ("Login Data", "name:browser-profile-db"),
        ("key4.db", "name:browser-profile-db"),
        ("logins.json", "name:browser-profile-db"),
        ("ｃｏｏｋｉｅｓ.txt", "name:cookies"),  # lebar-penuh dinormalisasi (NFKC)
    ],
)
def test_secret_looking_filenames_are_rejected(name: str, rule: str) -> None:
    finding = filename_finding(name)
    assert finding is not None and finding.rule == rule, (name, finding)
    decision = decide(ArtifactCapture(ArtifactKind.OTHER, name, b"x", "text/plain"))
    assert not decision.allowed and decision.rule == rule


@pytest.mark.parametrize(
    "name",
    [
        "shot.png", "halaman.html", "reply-1.json", "tweet_screenshot.png",
        "cookie-banner.png",  # tangkapan spanduk cookie: sah
        "session-01.png", "token-ring.png", "password-reset.html", "environment.html",
        "cookbook.html", "monkey.png", "keynote.png", "harga.html", "archive.zip",
    ],
)
def test_ordinary_filenames_are_not_flagged(name: str) -> None:
    assert not is_secret_filename(name), name


# =============================== tipe konten ===============================


@pytest.mark.parametrize(
    "ctype",
    ["application/x-har+json", "application/har+json", "application/x-pem-file",
     "application/pkcs12", "application/x-sqlite3", "application/vnd.sqlite3",
     "Application/X-SQLite3; charset=binary"],
)
def test_secret_containers_are_rejected_by_content_type(ctype: str) -> None:
    decision = decide(ArtifactCapture(ArtifactKind.OTHER, "data.bin", b"\x00", ctype))
    assert not decision.allowed and decision.rule == "type:secret-container"


# =============================== isi: positif dan negatif per aturan ===============================

POSITIVES = {
    "content:private-key": f"<pre>{PEM}\nMIIEvQIBADANBgkq\n</pre>",
    "content:authorization-header": "GET /x HTTP/1.1\nAuthorization: Bearer abcdef1234567890xyz\n",
    "content:cookie-header": "HTTP/1.1 200 OK\r\nSet-Cookie: theme=dark_mode_value; Path=/\r\n",
    "content:jwt": f'<script>var t="{JWT}";</script>',
    "content:session-cookie": f"document.cookie = 'sessionid={SESSION_VALUE}; path=/'",
    "content:session-cookie-short": "x; ct0=" + "f" * 32 + "; y",
    "content:credential-in-url": "<a href='https://admin:hunter22pw@intranet.example/panel'>x</a>",
    "content:token-query-param": '<img src="https://cdn.example/a.png?access_token=abcdef0123456789">',
    "content:secret-assignment": 'config = {"client_secret": "abcd1234efgh5678ijkl"}',
    "content:provider-token": f"aws_key = {AWS}",
}


@pytest.mark.parametrize(("rule", "text"), POSITIVES.items())
def test_each_content_rule_detects_a_credential(rule: str, text: str) -> None:
    decision = decide(dom(text))
    assert not decision.allowed and decision.rule == rule, (rule, decision)
    assert "byte" in decision.reason  # posisi dicatat


@pytest.mark.parametrize(
    "token",
    [GH, SLACK, GOOGLE, STRIPE],
)
def test_provider_token_formats_are_detected(token: str) -> None:
    assert decide(dom(f"<code>{token}</code>")).rule == "content:provider-token"


NEGATIVES = [
    "<p>Kami memakai cookies untuk meningkatkan pengalaman Anda.</p><button>Terima cookies</button>",
    "<div class='cookie-banner'>Cookie settings</div>",
    "<p>Authorization required to view this tweet.</p>",
    "<p>Your session token has expired; please log in again.</p>",
    "<input type='password' name='password' placeholder='Kata sandi'>",
    "<label>Password: <input name='pw'></label>",
    "<a href='https://x.com/user/status/123?s=20&t=abc'>tautan</a>",
    "<a href='https://example.com/page?utm_source=x&ref=y'>tautan</a>",
    "<meta name='csrf-token' content='abcdef'>",
    "<p>Bearer adalah kata dalam kalimat biasa tanpa kredensial.</p>",
    "<p>Perusahaan tidak perlu diaudit. #BakarHutan https://t.co/AbCdEf</p>",
    "{\"text\": \"Setuju sekali!\", \"id\": \"1234567890\", \"user\": \"alice\"}",
    "<p>Hubungi admin: admin@example.com atau https://example.com/kontak</p>",
    "<pre>cookie = secure and httponly flags are documented here</pre>",
    "x = {\"token\": \"short\"}",  # nilai terlalu pendek untuk menjadi rahasia
]


@pytest.mark.parametrize("text", NEGATIVES)
def test_benign_pages_are_not_rejected(text: str) -> None:
    assert decide(dom(text)).allowed, text


def test_rule_ids_never_leak_the_secret_value() -> None:
    for text in POSITIVES.values():
        decision = decide(dom(text))
        for secret in (SESSION_VALUE, "hunter22pw", "abcdef1234567890xyz", "abcd1234efgh5678ijkl", JWT):
            assert secret not in decision.reason and secret not in decision.rule


# =============================== catatan dan jenis konten ===============================


def test_a_secret_in_the_artifact_note_rejects_the_artifact() -> None:
    capture = ArtifactCapture(
        ArtifactKind.SCREENSHOT, "shot.png", b"\x89PNG", "image/png",
        note=f"diambil dengan Authorization: Bearer {'a' * 20}",
    )
    decision = decide(capture)
    assert not decision.allowed and decision.rule == "content:authorization-header"
    assert "catatan" in decision.reason


def test_images_and_media_are_not_content_scanned() -> None:
    """Batas yang diketahui (ADR 0011): kredensial di piksel/metadata gambar tidak dideteksi."""
    png_with_text = b"\x89PNG\r\n" + f"Authorization: Bearer {'a' * 20}".encode()
    for kind, ctype in [(ArtifactKind.SCREENSHOT, "image/png"), (ArtifactKind.MEDIA, "video/mp4")]:
        assert decide(ArtifactCapture(kind, "m.bin", png_with_text, ctype)).allowed


def test_binary_content_types_are_skipped_even_for_text_kinds() -> None:
    """Respons mentah/DOM bertipe gambar atau media dianggap biner: tidak dipindai sebagai teks
    (menghindari false positive pada byte acak). Batas yang diketahui, lihat ADR 0011."""
    body = b"\x89PNG\r\n" + f"Authorization: Bearer {'a' * 20}".encode()
    for kind in (ArtifactKind.RAW_RESPONSE, ArtifactKind.DOM_SNAPSHOT):
        for ctype in ("image/png", "video/mp4", "audio/mpeg", "font/woff2"):
            assert decide(ArtifactCapture(kind, "m.bin", body, ctype)).allowed, (kind, ctype)


def test_text_content_types_and_dom_kinds_are_scanned_even_with_odd_types() -> None:
    secret = f"Authorization: Bearer {'a' * 20}"
    for ctype in ("text/plain", "application/json", "application/octet-stream", "text/html; charset=utf-8"):
        capture = ArtifactCapture(ArtifactKind.RAW_RESPONSE, "r.dat", secret.encode(), ctype)
        assert not decide(capture).allowed, ctype
    plain = ArtifactCapture(ArtifactKind.OTHER, "n.txt", secret.encode(), "text/plain")
    assert not decide(plain).allowed


# =============================== aliran: batas potongan, UTF-16, ukuran ===============================


def stream(parts: list[bytes]) -> ArtifactCapture:
    return ArtifactCapture(
        ArtifactKind.DOM_SNAPSHOT, "besar.html", None, "text/html", chunks=lambda: iter(parts)
    )


def test_a_secret_split_across_chunk_boundaries_is_still_detected() -> None:
    secret = f"Authorization: Bearer {'z' * 24}".encode()
    for cut in (1, 5, len(secret) // 2, len(secret) - 1):
        decision = decide(stream([b"<p>awal</p>" + secret[:cut], secret[cut:] + b"<p>akhir</p>"]))
        assert not decision.allowed, cut
        assert decision.rule == "content:authorization-header"


def test_a_secret_far_into_a_large_stream_is_found_with_its_offset() -> None:
    filler = b"<p>teks biasa tanpa kredensial</p>\n" * 400
    parts = [filler] * 30 + [f"Cookie: sid=abcdefgh12345678;".encode()] + [filler] * 5
    decision = decide(stream(parts))
    assert not decision.allowed and decision.rule == "content:cookie-header"
    expected = 30 * len(filler)
    offset = int(decision.reason.split("byte ")[1].rstrip(")"))
    assert expected - OVERLAP <= offset <= expected + 8


def test_a_large_benign_stream_passes_without_loading_it_all() -> None:
    filler = b"<p>teks biasa tanpa kredensial sama sekali</p>\n" * 2000
    assert decide(stream([filler] * 100)).allowed  # sekitar 9 MB


def test_utf16_encoded_text_is_decoded_before_scanning() -> None:
    body = f"<html>Authorization: Bearer {'q' * 24}</html>".encode("utf-16")
    assert body[:2] in (b"\xff\xfe", b"\xfe\xff")
    decision = decide(dom(body))
    assert not decision.allowed and decision.rule == "content:authorization-header"
    halves = [body[: len(body) // 2], body[len(body) // 2 :]]
    assert not decide(stream(halves)).allowed  # juga bila terbelah di tengah


def test_scan_bytes_returns_none_for_clean_input_and_empty_streams() -> None:
    assert scan_bytes([]) is None
    assert scan_bytes([b"", b""]) is None
    assert scan_bytes([b"halo dunia"]) is None


# =============================== gagal tertutup ===============================


def test_unreadable_artifact_content_is_rejected_not_allowed() -> None:
    def broken():
        yield b"<p>separuh"
        raise RuntimeError("sumber putus")

    capture = ArtifactCapture(ArtifactKind.DOM_SNAPSHOT, "r.html", None, "text/html", chunks=broken)
    decision = decide(capture)
    assert not decision.allowed and decision.rule == "scan-error"
    assert "sumber putus" not in decision.reason  # pesan galat tidak diteruskan


# =============================== ketahanan terhadap input jahat (ReDoS) ===============================


@pytest.mark.parametrize(
    "payload",
    [
        b"a" * 2_000_000,
        b"cookie:" * 200_000,
        b"authorization: bearer " + b"a" * 1_000_000,
        b"set-cookie: x=" + b"=" * 1_000_000,
        b"password=" + b"a" * 15 + b"\n" * 100_000,
        b"https://" + b"a:" * 300_000,
        b"sessionid=" + b"%" * 1_000_000,
        (b"?token=" + b"x" * 10 + b"&") * 100_000,
        b"\n" * 300_000 + b"x",
        b"\r\n" * 150_000,
        b"' " * 300_000,
        b"\n  " * 200_000,
        b'"' * 500_000 + b" " * 500_000,
        b"cookie " * 100_000,
        b"sessionid " * 100_000,
    ],
    ids=["datar", "cookie-berulang", "bearer-panjang", "set-cookie-panjang", "baris-kosong",
         "url-berulang", "nilai-panjang", "parameter-berulang", "newline-saja", "crlf-saja",
         "kutip-spasi", "newline-spasi", "kutip-lalu-spasi", "cookie-spasi", "sessionid-spasi"],
)
def test_adversarial_inputs_are_scanned_in_bounded_time(payload: bytes) -> None:
    started = time.perf_counter()
    decide(dom(payload))
    assert time.perf_counter() - started < 10, "pemindaian terlalu lambat (kemungkinan ReDoS)"


# =============================== dokumen: aturan ada dan terdaftar ===============================


def test_every_content_rule_has_a_positive_example() -> None:
    from preservation.secret_filter import _CONTENT_RULES

    assert {rule for rule, _d, _p in _CONTENT_RULES} == set(POSITIVES), (
        "setiap aturan isi wajib punya contoh positif di tes ini"
    )


def test_filter_does_not_log_artifact_content(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        for text in POSITIVES.values():
            decide(dom(text))
    for secret in (SESSION_VALUE, "hunter22pw", "abcdef1234567890xyz", JWT):
        assert secret not in caplog.text
