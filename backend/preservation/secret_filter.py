"""Penyaring rahasia untuk artefak preservasi (WP-1.5b; PRD bagian 10 dan 13).

Cookies, sesi browser, token, dan kunci adalah kredensial rahasia: tidak boleh masuk arsip bukti,
Git, log, maupun keluaran AI. `SecretFilterPolicy` menolak artefak yang:
  1. namanya menyerupai berkas rahasia (cookies, storage_state, HAR, kunci, .env, basis data profil
     browser, ...);
  2. bertipe konten berkas rahasia/profil (HAR, PEM, PKCS#12, SQLite);
  3. isi teksnya memuat kredensial (blok kunci privat, header Authorization/Cookie, JWT, pasangan
     cookie sesi, kredensial di URL, parameter token, penugasan rahasia, token penyedia umum);
  4. `note`-nya memuat kredensial.

Prinsip:
- MENOLAK, bukan menyunting: menyunting akan mengubah bukti. Artefak ditolak tidak disimpan; alasan
  dicatat di manifest sebagai identitas aturan dan posisi byte, TIDAK PERNAH nilai atau cuplikannya.
- GAGAL TERTUTUP: bila pemindaian tidak dapat diselesaikan, artefak ditolak (`scan-error`).
- Pemindaian bersifat aliran dengan jendela tumpang-tindih sehingga kredensial yang terbelah di
  batas potongan tetap terdeteksi dan berkas besar tidak dimuat seluruhnya ke memori.

Ini PENDEKATAN HEURISTIK, bukan jaminan: lihat ADR 0011 untuk false negative dan false positive.
"""

import codecs
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from collection.contracts import ArtifactCapture, ArtifactKind

from .policy import PolicyDecision

# Jendela tumpang-tindih antar-potongan. Harus lebih besar daripada kecocokan minimum terpanjang
# di bawah (semua pola mensyaratkan paling banyak puluhan byte setelah penanda pembuka).
OVERLAP = 4096
SCAN_LIMIT_NOTE = 20_000


@dataclass(frozen=True)
class Finding:
    rule: str
    description: str
    offset: int | None = None


# --- aturan nama berkas (dicocokkan pada nama saja, tanpa membedakan huruf besar/kecil) ---------

_NAME_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "name:cookies",
        "nama berkas menyerupai ekspor/basis data cookies",
        re.compile(r"^cookies($|[._-])", re.I),
    ),
    (
        "name:storage-state",
        "nama berkas menyerupai status sesi browser",
        re.compile(r"^storage[_-]?state", re.I),
    ),
    ("name:har", "arsip HAR memuat header dan cookies", re.compile(r"\.har$", re.I)),
    (
        "name:key-material",
        "nama berkas menyerupai kunci/sertifikat privat",
        re.compile(r"(\.(pem|key|p12|pfx|kdbx|ppk)$|^id_(rsa|dsa|ecdsa|ed25519)(\.|$))", re.I),
    ),
    ("name:env-file", "berkas lingkungan (.env) memuat rahasia", re.compile(r"^\.env($|\.)", re.I)),
    (
        "name:secret-name",
        "nama berkas menyerupai kredensial/rahasia",
        re.compile(
            r"^(passwords?|passwd|secrets?|credentials?)(\.[a-z0-9]{1,8})?$"
            r"|[._-](secrets?|credentials?|tokens?)\.(json|txt|env|ini|conf|ya?ml|cfg)$",
            re.I,
        ),
    ),
    (
        "name:browser-profile-db",
        "berkas basis data profil browser",
        re.compile(
            r"^(login data|web data|local state|key[34]\.db|logins\.json|cert9\.db"
            r"|places\.sqlite|formhistory\.sqlite|cookies\.sqlite)$",
            re.I,
        ),
    ),
)

# --- aturan tipe konten ----------------------------------------------------------------------

_REJECTED_CONTENT_TYPES: dict[str, str] = {
    "application/x-har+json": "arsip HAR",
    "application/har+json": "arsip HAR",
    "application/x-pem-file": "berkas PEM",
    "application/x-x509-ca-cert": "sertifikat",
    "application/pkcs12": "keystore PKCS#12",
    "application/x-pkcs12": "keystore PKCS#12",
    "application/x-sqlite3": "basis data SQLite (profil browser)",
    "application/vnd.sqlite3": "basis data SQLite (profil browser)",
}

_TEXT_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "application/xhtml+xml",
    "application/javascript",
    "application/x-javascript",
    "application/x-www-form-urlencoded",
    "application/x-ndjson",
    "application/yaml",
    "application/x-yaml",
}
_TEXT_KINDS = {ArtifactKind.DOM_SNAPSHOT, ArtifactKind.RAW_RESPONSE}
_BINARY_PREFIXES = ("image/", "video/", "audio/", "font/")

# --- aturan isi (pola bytes; ASCII sehingga tak bergantung pada pengodean UTF-8/Latin-1) -------

_FLAGS = re.IGNORECASE | re.ASCII
_VALUE = rb"[A-Za-z0-9%._~+/=\-]"

_PRIVATE_KEY_HEADER = (
    b"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----"
)

_CONTENT_RULES: tuple[tuple[str, str, re.Pattern[bytes]], ...] = (
    ("content:private-key", "blok kunci privat", re.compile(_PRIVATE_KEY_HEADER)),
    (
        "content:authorization-header",
        "header Authorization berisi kredensial",
        re.compile(
            rb"\bauthorization\"?\s*[:=]\s*\"?(?:bearer|basic|token|oauth)\s+"
            rb"[A-Za-z0-9._~+/=\-]{8,}",
            _FLAGS,
        ),
    ),
    (
        "content:cookie-header",
        "header Cookie/Set-Cookie berisi nilai",
        re.compile(
            rb"(?:^|[\r\n\"'])[ \t]*(?:set-)?cookie\"?\s*[:=]\s*\"?[A-Za-z0-9_.\-%]{1,64}="
            rb"[^\r\n;\"]{6,}",
            _FLAGS,
        ),
    ),
    (
        "content:jwt",
        "token JWT",
        re.compile(
            rb"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", _FLAGS
        ),
    ),
    (
        "content:session-cookie",
        "pasangan cookie sesi bernilai",
        re.compile(
            rb"(?<![A-Za-z0-9_])(?:sessionid|ds_user_id|auth_token|c_user|li_at|sapisid"
            rb"|jsessionid|phpsessid|connect\.sid)\s*=\s*" + _VALUE + rb"{8,}",
            _FLAGS,
        ),
    ),
    (
        "content:session-cookie-short",
        "cookie sesi platform bernilai panjang",
        re.compile(
            rb"(?<![A-Za-z0-9_])(?:ct0|xs|sid|datr|csrftoken)\s*=\s*" + _VALUE + rb"{16,}", _FLAGS
        ),
    ),
    (
        "content:credential-in-url",
        "kredensial di dalam URL",
        re.compile(rb"\bhttps?://[^\s/@:\"'<>]{1,64}:[^\s/@\"'<>]{3,}@", _FLAGS),
    ),
    (
        "content:token-query-param",
        "parameter token pada URL",
        re.compile(
            rb"[?&;](?:access_token|refresh_token|id_token|auth_token|api_key|apikey"
            rb"|client_secret)=" + _VALUE + rb"{12,}",
            _FLAGS,
        ),
    ),
    (
        "content:secret-assignment",
        "penugasan nilai rahasia",
        re.compile(
            rb"[\"']?(?:client_secret|api[_-]?secret|secret[_-]?key|password|passwd"
            rb"|access[_-]?token|refresh[_-]?token|auth[_-]?token|private[_-]?key)[\"']?"
            rb"\s*[:=]\s*[\"']?[A-Za-z0-9/+_=.\-]{16,}",
            _FLAGS,
        ),
    ),
    (
        "content:provider-token",
        "token penyedia layanan",
        re.compile(
            rb"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9\-]{10,}"
            rb"|AIza[0-9A-Za-z_\-]{35}|sk_live_[0-9A-Za-z]{16,})\b"
        ),
    ),
)


def filename_finding(name: str) -> Finding | None:
    normalized = unicodedata.normalize("NFKC", name)
    for rule, description, pattern in _NAME_RULES:
        if pattern.search(normalized):
            return Finding(rule, description)
    return None


def is_secret_filename(name: str) -> bool:
    return filename_finding(name) is not None


def _is_text_like(capture: ArtifactCapture) -> bool:
    ctype = capture.content_type.split(";")[0].strip().lower()
    if ctype.startswith(_BINARY_PREFIXES):
        return False
    return ctype.startswith("text/") or ctype in _TEXT_TYPES or capture.kind in _TEXT_KINDS


def scan_bytes(chunks: Iterable[bytes]) -> Finding | None:
    """Pindai aliran bytes dengan jendela tumpang-tindih; kembalikan temuan pertama.

    Aliran ber-BOM UTF-16 didekode secara inkremental ke UTF-8 agar pola ASCII tetap cocok."""
    decoder = None
    tail = b""
    consumed = 0
    for index, raw in enumerate(chunks):
        if index == 0 and raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            decoder = codecs.getincrementaldecoder("utf-16")(errors="replace")
        chunk = decoder.decode(raw).encode("utf-8", "replace") if decoder else raw
        window = tail + chunk
        for rule, description, pattern in _CONTENT_RULES:
            match = pattern.search(window)
            if match:
                return Finding(rule, description, consumed - len(tail) + match.start())
        consumed += len(chunk)
        tail = window[-OVERLAP:]
    return None


class SecretFilterPolicy:
    """Kebijakan produksi: menolak artefak yang menyerupai atau memuat kredensial."""

    def check(self, capture: ArtifactCapture) -> PolicyDecision:
        finding = filename_finding(capture.filename)
        if finding is None:
            finding = self._content_type_finding(capture)
        if finding is None and capture.note:
            noted = scan_bytes([capture.note[:SCAN_LIMIT_NOTE].encode("utf-8", "replace")])
            if noted:
                finding = Finding(noted.rule, f"catatan artefak: {noted.description}", noted.offset)
        if finding is None and _is_text_like(capture):
            try:
                finding = scan_bytes(capture.iter_chunks())
            except Exception:  # noqa: BLE001 - GAGAL TERTUTUP: tak dapat dipindai = tidak aman
                return PolicyDecision(
                    False,
                    "scan-error",
                    "isi tidak dapat dipindai sehingga tidak dapat dipastikan aman",
                )
        if finding is None:
            return PolicyDecision(True)
        where = f" (byte {finding.offset})" if finding.offset is not None else ""
        return PolicyDecision(False, finding.rule, f"{finding.description}{where}")

    @staticmethod
    def _content_type_finding(capture: ArtifactCapture) -> Finding | None:
        ctype = capture.content_type.split(";")[0].strip().lower()
        if ctype in _REJECTED_CONTENT_TYPES:
            return Finding("type:secret-container", _REJECTED_CONTENT_TYPES[ctype])
        return None
