"""Isi kanonik dan hash isi untuk mendeteksi perubahan antar-run (WP-1.4; FR-035, AT-05).

Definisi "perubahan relevan" (aturan versi 1, `CONTENT_HASH_VERSION`):
  jenis objek, TEKS, penulis (ID), induk (atau 'induk tidak diketahui'), objek yang dikutip,
  objek yang di-repost, dan himpunan akun yang disebut.
TIDAK dihitung: `observed_at`/`captured_at` (selalu berbeda antar-run), username/nama tampilan
(dapat berubah dan dicatat per observasi), `collection_status`, dan flag verifikasi identitas.
`published_at` dibandingkan terpisah: hanya jika KEDUANYA diketahui dan berbeda.

Normalisasi teks (agar perbedaan render tidak memicu MODIFIED): Unicode NFC; baris baru
disamakan ke '\\n'; spasi/tab beruntun menjadi satu spasi dan tepi baris dipangkas; tiga baris
kosong atau lebih menjadi dua; spasi lebar-nol (U+200B) dan BOM (U+FEFF) dibuang; tepi teks
dipangkas. Konsekuensi: perubahan yang HANYA mengubah spasi atau baris kosong tidak terdeteksi
sebagai perubahan (teks mentah tetap tersimpan utuh pada observasi). `None` (tidak tersedia)
dibedakan dari teks kosong.

Aturan ini adalah asumsi kerja yang berversi: bila diubah, naikkan `CONTENT_HASH_VERSION`; hash
beda versi tidak dibandingkan langsung, tetapi dihitung ulang dari data mentah.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass

from .contracts import Observation

CONTENT_HASH_VERSION = 1

_INLINE_SPACE = re.compile(r"[ \t ]+")
_BLANK_RUNS = re.compile(r"\n{3,}")
_INVISIBLE = str.maketrans("", "", "​﻿")

# Urutan tetap agar keluaran `diff` deterministik.
FIELDS = ("type", "text", "author", "parent", "quoted", "reposted", "mentions")


def normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    value = unicodedata.normalize("NFC", text).translate(_INVISIBLE)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "\n".join(_INLINE_SPACE.sub(" ", line).strip() for line in value.split("\n"))
    return _BLANK_RUNS.sub("\n\n", value).strip("\n")


@dataclass(frozen=True)
class CanonicalContent:
    type: str
    text: str | None
    author: str | None
    parent: str | None
    parent_unknown: bool
    quoted: str | None
    reposted: str | None
    mentions: tuple[str, ...]

    def digest(self) -> str:
        payload = {"v": CONTENT_HASH_VERSION, **asdict(self)}
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def diff(self, other: "CanonicalContent") -> list[str]:
        """Nama atribut relevan yang berbeda (kosong = tidak ada perubahan relevan)."""
        changed = []
        for name in FIELDS:
            if name == "parent":
                differs = (self.parent, self.parent_unknown) != (other.parent, other.parent_unknown)
            else:
                differs = getattr(self, name) != getattr(other, name)
            if differs:
                changed.append(name)
        return changed


def canonical(
    *,
    object_type: str,
    text: str | None,
    author: str | None,
    parent: str | None,
    parent_unknown: bool,
    quoted: str | None = None,
    reposted: str | None = None,
    mentions: tuple[str, ...] | list[str] = (),
) -> CanonicalContent:
    return CanonicalContent(
        type=object_type,
        text=normalize_text(text),
        author=author,
        parent=parent,
        parent_unknown=parent_unknown,
        quoted=quoted,
        reposted=reposted,
        mentions=tuple(sorted(set(mentions))),
    )


def canonical_from_observation(o: Observation) -> CanonicalContent:
    return canonical(
        object_type=o.source_object_type.value,
        text=o.text,
        author=o.external_actor_id,
        parent=o.parent_post_id,
        parent_unknown=o.parent_unknown,
        quoted=o.quoted_post_id,
        reposted=o.reposted_post_id,
        mentions=o.mentioned_actor_ids,
    )


def observation_content_hash(o: Observation) -> str:
    return canonical_from_observation(o).digest()
