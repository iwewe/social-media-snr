"""Generator dataset sintetis I2 (WP-2.0; PRD 16.1, Lampiran A).

Deterministik (seed tetap), tanpa dependensi Django. Menghasilkan:
- `datasets/*.json`: berkas dataset format v1 (`docs/format-dataset-impor.md`), seluruhnya
  `synthetic_fixture`;
- `ground-truth.json`: kunci jawaban TERPISAH (sengaja di luar direktori dataset agar adapter
  tidak membacanya).

Semua akun, nama, tautan, dan peristiwa fiktif; tidak meniru orang atau akun nyata. Pola
"terkoordinasi" yang ditanam hanya bahan uji indikator (ADR 0024), bukan pernyataan tentang pihak
mana pun.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_SEED = 20261018
SCHEMA_VERSION = 1
POST_TIME = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
SNAPSHOT_HOURS = (12, 24, 36, 48)  # snapshot ke-k diamati pada POST_TIME + jam ke-k
REPLIES_PER_TARGET = 100
COORDINATED_URL = "https://contoh-berita.example/klarifikasi"
ORGANIC_SHARED_URL = "https://contoh-berita.example/laporan-populer"

ORGANIC_PRO = [f"s{i:02d}" for i in range(1, 13)]
ORGANIC_CONTRA = [f"s{i:02d}" for i in range(13, 25)]
ASKERS = [f"s{i:02d}" for i in range(25, 31)]
ATTACKERS = [f"s{i:02d}" for i in range(31, 37)]
COORDINATED = [f"s{i:02d}" for i in range(37, 47)]
PARTIAL_ONLY_T1 = "s47"
POSTERS = {1: "s50", 2: "s49", 3: "s48"}
ALL_ACCOUNTS = [f"s{i:02d}" for i in range(1, 51)]
ORGANIC = ORGANIC_PRO + ORGANIC_CONTRA + ASKERS

PRO, CONTRA, UNDETERMINED, NOT_RELEVANT = "PRO", "CONTRA", "UNDETERMINED", "NOT_RELEVANT"
SUPPORT, OPPOSE, UNCLEAR = "SUPPORT", "OPPOSE", "UNCLEAR"


@dataclass(frozen=True)
class TargetConfig:
    n: int
    url: str
    seed_text: str
    seed_stance: str
    pro_claim: str
    contra_claim: str
    media: bool = False


TARGETS = (
    TargetConfig(
        1,
        "https://x.com/contoh_redaksi/status/9100000001",
        "Perusahaan tidak perlu diaudit.",
        CONTRA,
        "perusahaan yang diduga terkait kebakaran hutan itu harus diaudit",
        "perusahaan itu tidak perlu diaudit",
    ),
    TargetConfig(
        2,
        "https://x.com/contoh_redaksi/status/9100010001",
        "Anggaran desa harus dibuka ke publik.",
        PRO,
        "anggaran desa harus dibuka ke publik",
        "anggaran desa tidak perlu dipublikasikan",
    ),
    TargetConfig(
        3,
        "https://x.com/contoh_redaksi/status/9100020001",
        "Lihat video ini, tarif parkir baru memberatkan.",
        PRO,
        "tarif parkir baru harus dicabut",
        "tarif parkir baru sudah wajar",
        media=True,
    ),
)

# (teks, label); {claim} diisi pro/contra target.
_PRO_FORMS = [
    "Menurut saya {claim}.",
    "Jelas sekali {claim}.",
    "Intinya sederhana: {claim}.",
    "Kalau mau adil, {claim}.",
    "Saya mendukung, {claim}.",
    "Sulit membantah bahwa {claim}.",
    "Tidak ada alasan menunda, {claim}.",
    "Warga berhak menuntut agar {claim}.",
]
_PREFIX = ["", "Jujur, ", "Hmm, ", "Maaf ya, ", "Sekadar info, ", "Catatan saya: "]
_SUFFIX = ["", " Sekian.", " Itu pendapat saya.", " Terima kasih.", " 🙏", " wkwk"]
_ASK = [
    "Apa buktinya?",
    "Sumbernya dari mana?",
    "Boleh tahu datanya dari mana?",
    "Ada dokumen resminya?",
]
_EMOTION = [
    "Saya marah melihat kejadian ini.",
    "Sedih sekali membaca ini.",
    "Capek banget lihat berita begini.",
]
_ATTACK = [
    "Penulis ini bodoh.",
    "Kamu ini tidak mengerti apa-apa.",
    "Akun ini isinya sampah.",
    "Orang seperti ini memang pantas diabaikan.",
]
_SARCASM = [
    "Wah hebat sekali, pasti semua pihak sudah puas ya.",
    "Oh tentu, semuanya pasti baik-baik saja.",
    "Luar biasa, jenius banget logikanya.",
]
_OFFTOPIC = ["Ada yang tahu resep nasi goreng enak?", "Kemarin hujan deras banget di tempatku."]
_SPAM = ["Jual follower murah, cek bio ya.", "Promo diskon besar hari ini!"]
_THREAT = ["Awas ya, urusannya bisa panjang kalau kamu terus begini."]
_CRITICISM = [
    "Argumen ini lemah karena tidak mencantumkan sumber datanya.",
    "Klaim ini belum disertai rujukan yang bisa dicek.",
]
_VIDEO = ["Lihat videonya, jelas banget itu.", "Di menit ke-2 itu sudah kelihatan semuanya."]
_AGREE = ["Setuju sekali!", "Betul, saya sependapat.", "Sama, aku juga mikir begitu."]
_DISAGREE = ["Tidak sependapat, menurut saya itu keliru.", "Saya kurang setuju dengan ini."]
_COORD_BASE = [
    "Kasus ini sudah dijelaskan lengkap di sini, sebaiknya semua membaca dulu sebelum berkomentar",
    "Sebelum menghakimi, baca klarifikasi resminya dulu",
]


@dataclass
class _Entry:
    key: str
    target: int
    actor: str
    kind: str  # post | reply | repost
    published: datetime
    text: str
    parent_key: str | None
    truth: dict[str, Any]
    case: str | None = None
    id: str = ""


@dataclass
class Bundle:
    datasets: dict[str, dict[str, Any]]
    ground_truth: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)


def _informal(text: str, flip: bool) -> str:
    if not flip:
        return text
    for a, b in (("tidak", "nggak"), ("sudah", "udah"), ("saya", "aku"), ("Saya", "Aku")):
        text = text.replace(a, b)
    return text


def _phrase(rng: random.Random, template: str, informal: bool) -> str:
    prefix, suffix = rng.choice(_PREFIX), rng.choice(_SUFFIX)
    body = template
    if prefix:
        body = body[0].lower() + body[1:]
    return _informal(prefix + body + suffix, informal)


def _truth(
    stance: str,
    alignment: str,
    characters: list[str],
    *,
    sentiment: str | None = None,
    group: str = "organic",
    human_review: bool = False,
    sarcastic: bool = False,
    media_dependent: bool = False,
) -> dict[str, Any]:
    return {
        "issue_stance": stance,
        "target_alignment": alignment,
        "expression_sentiment": sentiment,
        "response_character": characters,
        "needs_human_review": human_review,
        "sarcastic": sarcastic,
        "media_dependent": media_dependent,
        "group": group,
    }


def _alignment(stance: str, parent_stance: str) -> str:
    if stance in (PRO, CONTRA) and parent_stance in (PRO, CONTRA):
        return SUPPORT if stance == parent_stance else OPPOSE
    return UNCLEAR


def _flip(stance: str) -> str:
    return {PRO: CONTRA, CONTRA: PRO}.get(stance, stance)


def _generic_reply(
    rng: random.Random,
    cfg: TargetConfig,
    actor: str,
    informal: bool,
    parent: _Entry | None,
) -> tuple[str, dict[str, Any], str | None]:
    """Satu balasan organik/penyerang menurut peran akun: (teks, kunci jawaban, parent_key)."""
    seed_stance = cfg.seed_stance
    if actor in ORGANIC_PRO or actor in ORGANIC_CONTRA:
        mine = PRO if actor in ORGANIC_PRO else CONTRA
        roll = rng.random()
        if roll < 0.22 and parent is not None and parent.truth["issue_stance"] in (PRO, CONTRA):
            ps = parent.truth["issue_stance"]
            if rng.random() < 0.7:
                return (
                    _informal(rng.choice(_AGREE), informal),
                    _truth(ps, SUPPORT, ["RC-01"]),
                    parent.key,
                )
            return (
                _informal(rng.choice(_DISAGREE), informal),
                _truth(_flip(ps), OPPOSE, ["RC-03"]),
                parent.key,
            )
        if roll < 0.30:
            return (
                _informal(rng.choice(_CRITICISM), informal),
                _truth(UNDETERMINED, OPPOSE, ["RC-02"]),
                None,
            )
        claim = cfg.pro_claim if mine == PRO else cfg.contra_claim
        text = _phrase(rng, rng.choice(_PRO_FORMS).format(claim=claim), informal)
        character = "RC-01" if mine == seed_stance else "RC-03"
        return text, _truth(mine, _alignment(mine, seed_stance), [character]), None
    if actor in ASKERS:
        roll = rng.random()
        if roll < 0.4:
            return (
                _informal(rng.choice(_ASK), informal),
                _truth(UNDETERMINED, UNCLEAR, ["RC-04"]),
                None,
            )
        if roll < 0.7:
            return (
                _informal(rng.choice(_EMOTION), informal),
                _truth(UNDETERMINED, UNCLEAR, ["RC-10"], sentiment="NEGATIVE"),
                None,
            )
        if roll < 0.82:
            return (
                rng.choice(_OFFTOPIC),
                _truth(NOT_RELEVANT, UNCLEAR, ["RC-08"]),
                None,
            )
        if roll < 0.9:
            return rng.choice(_SPAM), _truth(NOT_RELEVANT, UNCLEAR, ["RC-09"]), None
        if cfg.media:
            return (
                rng.choice(_VIDEO),
                _truth(UNDETERMINED, UNCLEAR, ["RC-10"], media_dependent=True),
                None,
            )
        return (
            rng.choice(_SARCASM),
            _truth(UNDETERMINED, UNCLEAR, ["RC-06"], sarcastic=True),
            None,
        )
    # penyerang personal: bukan koordinasi; waktu dan teks independen
    roll = rng.random()
    if roll < 0.75:
        return (
            _informal(rng.choice(_ATTACK), informal),
            _truth(UNDETERMINED, UNCLEAR, ["RC-05"], group="attacker"),
            None,
        )
    if roll < 0.9:
        return (
            rng.choice(_SARCASM),
            _truth(UNDETERMINED, UNCLEAR, ["RC-06"], group="attacker", sarcastic=True),
            None,
        )
    return (
        rng.choice(_THREAT),
        _truth(UNDETERMINED, UNCLEAR, ["RC-07"], group="attacker", human_review=True),
        None,
    )


def _coordinated_text(rng: random.Random, with_url: bool) -> str:
    base = rng.choice(_COORD_BASE)
    variants = [base, base + ".", base.lower(), base + "!", base.replace("sebaiknya ", "")]
    text = rng.choice(variants)
    return f"{text} {COORDINATED_URL}-{rng.choice([1, 1, 1, 2])}" if with_url else text


def _build_target(cfg: TargetConfig, seed: int) -> list[_Entry]:
    rng = random.Random(f"{seed}-{cfg.n}")
    informal = {a: rng.random() < 0.4 for a in ALL_ACCOUNTS}
    poster = POSTERS[cfg.n]
    entries: list[_Entry] = [
        _Entry(
            f"t{cfg.n}-post",
            cfg.n,
            poster,
            "post",
            POST_TIME,
            cfg.seed_text,
            None,
            _truth(cfg.seed_stance, UNCLEAR, [], group="seed"),
        )
    ]
    seed_key = entries[0].key

    def at(seconds: float) -> datetime:
        return POST_TIME + timedelta(seconds=int(seconds))

    def reply(key, actor, seconds, text, parent_key, truth, case=None):
        entries.append(
            _Entry(key, cfg.n, actor, "reply", at(seconds), text, parent_key, truth, case)
        )

    # Kasus tetap (Lampiran A PRD) pada target 1 + pasangan kritik sah/serangan pada target 2.
    if cfg.n == 1:
        reply(
            "t1-c1",
            "s03",
            3600,
            "Justru audit harus dilakukan.",
            seed_key,
            _truth(PRO, OPPOSE, ["RC-03"]),
            "A-R1",
        )
        reply(
            "t1-c2",
            "s07",
            4200,
            "Setuju sekali!",
            "t1-c1",
            _truth(PRO, SUPPORT, ["RC-01"]),
            "A-R2-setuju-pada-reply-tingkat-2",
        )
        reply(
            "t1-c3",
            "s31",
            7200,
            "Penulis ini bodoh.",
            seed_key,
            _truth(UNDETERMINED, UNCLEAR, ["RC-05"], group="attacker"),
            "A-R3",
        )
        reply(
            "t1-c4",
            "s26",
            10800,
            "Apa bukti keterlibatannya?",
            seed_key,
            _truth(UNDETERMINED, UNCLEAR, ["RC-04"]),
            "A-R4",
        )
        reply(
            "t1-c5",
            "s27",
            14400,
            "Saya marah melihat kebakaran ini.",
            seed_key,
            _truth(UNDETERMINED, UNCLEAR, ["RC-10"], sentiment="NEGATIVE"),
            "A-R5",
        )
        reply(
            "t1-p1",
            PARTIAL_ONLY_T1,
            20000,
            "Perusahaan itu harus diaudit, kita butuh datanya.",
            seed_key,
            _truth(PRO, OPPOSE, ["RC-03"]),
            "AT-17-cakupan-sebagian",
        )
    if cfg.n == 2:
        reply(
            "t2-c1",
            "s15",
            9000,
            "Argumen ini lemah karena tidak mencantumkan sumber datanya.",
            seed_key,
            _truth(UNDETERMINED, OPPOSE, ["RC-02"]),
            "AT-10-kritik-sah",
        )
        reply(
            "t2-c2",
            "s32",
            9600,
            "Penulis ini bodoh.",
            seed_key,
            _truth(UNDETERMINED, UNCLEAR, ["RC-05"], group="attacker"),
            "AT-10-serangan-pribadi",
        )
    if cfg.n == 3:
        reply(
            "t3-c1",
            "s28",
            5400,
            "Lihat videonya, jelas banget itu.",
            seed_key,
            _truth(UNDETERMINED, UNCLEAR, ["RC-10"], media_dependent=True),
            "AT-09-acuan-video",
        )

    # Ledakan organik awal: banyak akun berbeda membalas dalam hitungan menit dengan teks
    # berbeda (lawan uji CO-02).
    burst_pool = rng.sample(ORGANIC_PRO + ORGANIC_CONTRA, 8)
    for i, actor in enumerate(burst_pool):
        text, truth, _ = _generic_reply(rng, cfg, actor, informal[actor], None)
        truth["group"] = "organic-burst"
        reply(
            f"t{cfg.n}-b{i}",
            actor,
            rng.randint(60, 480),
            text,
            seed_key,
            truth,
            "organik-ledakan-awal",
        )

    # Tautan populer yang dibagikan organik (lawan uji CO-05) pada target 2.
    if cfg.n == 2:
        for i, actor in enumerate(rng.sample(ORGANIC_PRO, 5)):
            reply(
                f"t2-u{i}",
                actor,
                rng.randint(3 * 3600, 40 * 3600),
                f"Ini laporan lengkapnya {ORGANIC_SHARED_URL}",
                seed_key,
                _truth(UNDETERMINED, UNCLEAR, ["RC-10"], group="organic-shared-url"),
                "organik-tautan-populer",
            )

    # Pola yang sengaja ditanam: kelompok K membalas induk yang sama dalam jendela sempit,
    # teks nyaris sama,
    # tautan sama, dan me-repost posting yang sama; berulang pada ketiga target.
    trigger = rng.randint(int(5.0 * 3600), int(6.0 * 3600))
    members = rng.sample(COORDINATED, 8)
    for i, actor in enumerate(members):
        offset = trigger + rng.randint(0, 90)
        reply(
            f"t{cfg.n}-k{i}",
            actor,
            offset,
            _coordinated_text(rng, with_url=rng.random() < 0.7),
            seed_key,
            _truth(UNDETERMINED, UNCLEAR, ["RC-10"], group="coordinated-planted"),
            "pola-ditanam-K",
        )
        entries.append(
            _Entry(
                f"t{cfg.n}-kr{i}",
                cfg.n,
                actor,
                "repost",
                at(offset + rng.randint(5, 60)),
                "",
                seed_key,
                _truth(UNDETERMINED, UNCLEAR, [], group="coordinated-planted"),
                "pola-ditanam-K",
            )
        )

    # Sisanya: partisipasi organik tersebar, peluruhan eksponensial dari waktu posting.
    organic_actors = ORGANIC + ATTACKERS
    weights = [3 if a in ORGANIC_PRO + ORGANIC_CONTRA else 1 for a in organic_actors]
    while sum(1 for e in entries if e.kind == "reply") < REPLIES_PER_TARGET:
        actor = rng.choices(organic_actors, weights)[0]
        seconds = min(rng.expovariate(1 / (14 * 3600)) + 600, 45 * 3600)
        parents = [
            e
            for e in entries
            if e.kind == "reply"
            and e.truth["group"] == "organic"
            and e.published < at(seconds)
            and e.truth["issue_stance"] in (PRO, CONTRA)
        ]
        parent = rng.choice(parents) if parents else None
        text, truth, parent_key = _generic_reply(rng, cfg, actor, informal[actor], parent)
        reply(f"t{cfg.n}-o{len(entries)}", actor, seconds, text, parent_key or seed_key, truth)
    return entries


def _assign_ids(entries: list[_Entry], base: int) -> None:
    ordered = sorted(entries, key=lambda e: (e.published, e.key))
    for i, e in enumerate(ordered):
        e.id = str(base + i + 1)


def _obs(e: _Entry, by_key: dict[str, _Entry], platform_handle: dict[str, str]) -> dict[str, Any]:
    o: dict[str, Any] = {
        "type": e.kind,
        "id": e.id,
        "actor": e.actor,
        "parent": by_key[e.parent_key].id if e.parent_key and e.kind == "reply" else None,
        "text": e.text if e.kind != "repost" else None,
        "published_at": e.published.isoformat().replace("+00:00", "Z"),
        "handle": platform_handle[e.actor],
        "display_name": f"Akun {e.actor.upper()}",
    }
    if e.kind == "repost":
        o["reposted"] = by_key[e.parent_key].id  # type: ignore[index]
        o["parent"] = None
    return o


def _iso(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


def _x_dataset(
    cfg: TargetConfig, entries: list[_Entry], rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_key = {e.key: e for e in entries}
    handles = {a: f"akun_{a}" for a in ALL_ACCOUNTS}
    handles[POSTERS[cfg.n]] = "contoh_redaksi"
    replies = sorted((e for e in entries if e.kind == "reply"), key=lambda e: e.published)
    parent_keys = {e.parent_key for e in entries}
    organic_pool = [
        e
        for e in replies
        if e.truth["group"] == "organic" and e.case is None and e.key not in parent_keys
    ]

    edited = rng.sample(
        [e for e in organic_pool if e.published <= POST_TIME + timedelta(hours=20)], 3
    )
    edit_suffix = " Update: sudah saya revisi."
    gone_partial: list[_Entry] = []
    gone_confirmed: list[_Entry] = []
    pool12 = [
        e
        for e in organic_pool
        if e.published <= POST_TIME + timedelta(hours=12) and e not in edited
    ]
    if cfg.n == 2:
        gone_partial = rng.sample(pool12, 4)
    if cfg.n == 1:
        gone_confirmed = rng.sample(pool12, 2)

    snapshots = []
    truth_changes: dict[str, Any] = {
        "edited": [],
        "missing_partial_snapshot_3": [],
        "confirmed_unavailable": [],
    }
    for k, hours in enumerate(SNAPSHOT_HOURS, start=1):
        observed = POST_TIME + timedelta(hours=hours)
        visible = [e for e in entries if e.published <= observed]
        omit: set[str] = set()
        if k == 3:
            omit |= {e.key for e in gone_partial}
        if k >= 3:
            omit |= {e.key for e in gone_confirmed}
        shown = [e for e in visible if e.key not in omit]
        observations = []
        for e in shown:
            o = _obs(e, by_key, handles)
            if e in edited and k >= 3 and o["text"]:
                o["text"] += edit_suffix
            observations.append(o)
        snap: dict[str, Any] = {
            "observed_at": _iso(observed),
            "outcome": "COMPLETED",
            "pagination_complete": True,
            "displayed_count": sum(1 for e in shown if e.kind == "reply"),
            "observations": observations,
            "notes": [f"Putaran {k} (sintetis)."],
        }
        if k == 3 and gone_partial:
            snap["outcome"] = "PARTIAL"
            snap["pagination_complete"] = False
            snap["displayed_count"] = sum(1 for e in visible if e.kind == "reply")
            snap["limitations"] = [
                {
                    "code": "PAGINATION_INCOMPLETE",
                    "message": "Pemuatan balasan berhenti sebelum selesai (simulasi).",
                }
            ]
        if k == 4 and gone_confirmed:
            snap["confirmed_unavailable"] = [
                {
                    "id": e.id,
                    "evidence": "Platform menampilkan 'balasan tidak tersedia' (simulasi).",
                }
                for e in gone_confirmed
            ]
        snapshots.append(snap)
    for e in edited:
        truth_changes["edited"].append(
            {"id": e.id, "from_snapshot": 3, "appended_text": edit_suffix}
        )
    truth_changes["missing_partial_snapshot_3"] = [e.id for e in gone_partial]
    truth_changes["confirmed_unavailable"] = [
        {"id": e.id, "from_snapshot": 4, "also_absent_in": [3, 4]} for e in gone_confirmed
    ]
    ds = {
        "schema_version": SCHEMA_VERSION,
        "name": f"SINTETIS-I2-target-{cfg.n}",
        "platform": "x",
        "target_url": cfg.url,
        "source_method": "synthetic_fixture",
        "snapshots": snapshots,
    }
    return ds, truth_changes


def _tiktok_dataset(
    x_entries: list[_Entry], rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Dataset TikTok kecil dengan handle yang SAMA dengan akun X (AT-13): tidak boleh digabung."""
    shared_handle_actor = COORDINATED[0]
    x_text = next(e.text for e in x_entries if e.actor == shared_handle_actor and e.kind == "reply")
    base = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
    comments = [
        {
            "type": "post",
            "id": "tt-9100000099",
            "actor": "tt-poster",
            "parent": None,
            "text": "Video penjelasan kebijakan parkir kampus (fiktif).",
            "published_at": _iso(base),
            "handle": "contoh_redaksi",
            "display_name": "Akun TT-POSTER",
        },
        {
            "type": "comment",
            "id": "tt-c-1",
            "actor": "tt-1",
            "parent": "tt-9100000099",
            "text": x_text,
            "published_at": _iso(base + timedelta(minutes=30)),
            "handle": f"akun_{shared_handle_actor}",
            "display_name": "Akun di TikTok",
        },
    ]
    for i in range(2, 20):
        comments.append(
            {
                "type": "comment",
                "id": f"tt-c-{i}",
                "actor": f"tt-{i}",
                "parent": "tt-9100000099",
                "text": rng.choice(_ASK + _EMOTION + _OFFTOPIC),
                "published_at": _iso(base + timedelta(minutes=30 + i * 11)),
                "handle": f"akun_tt{i:02d}",
                "display_name": f"Akun TT{i:02d}",
            }
        )
    ds = {
        "schema_version": SCHEMA_VERSION,
        "name": "SINTETIS-I2-tiktok-handle-sama",
        "platform": "tiktok",
        "target_url": "https://www.tiktok.com/@contoh_redaksi/video/9100000099",
        "source_method": "synthetic_fixture",
        "snapshots": [
            {
                "observed_at": _iso(base + timedelta(hours=12)),
                "outcome": "COMPLETED",
                "pagination_complete": True,
                "displayed_count": len(comments) - 1,
                "observations": comments,
            }
        ],
    }
    truth = {
        "shared_handle": f"akun_{shared_handle_actor}",
        "x_actor": shared_handle_actor,
        "tiktok_actor": "tt-1",
        "expectation": "akun, graf, dan profil TIDAK digabung lintas platform (AT-13)",
    }
    return ds, truth


def generate(seed: int = DEFAULT_SEED) -> Bundle:
    datasets: dict[str, dict[str, Any]] = {}
    truth_targets: dict[str, Any] = {}
    all_entries: list[_Entry] = []
    for cfg in TARGETS:
        entries = _build_target(cfg, seed)
        _assign_ids(entries, 9100000000 + (cfg.n - 1) * 10000)
        post = next(e for e in entries if e.kind == "post")
        assert post.id == cfg.url.rsplit("/", 1)[1], (
            "id posting harus sama dengan id pada URL target"
        )
        rng = random.Random(f"{seed}-ds-{cfg.n}")
        ds, changes = _x_dataset(cfg, entries, rng)
        datasets[f"x-target-{cfg.n}.json"] = ds
        all_entries.extend(entries)
        truth_targets[str(cfg.n)] = {
            "target_url": cfg.url,
            "seed_stance": cfg.seed_stance,
            "changes": changes,
            "observations": {
                e.id: {
                    "key": e.key,
                    "actor": e.actor,
                    "kind": e.kind,
                    "parent": next((p.id for p in entries if p.key == e.parent_key), None),
                    "case": e.case,
                    **e.truth,
                }
                for e in entries
            },
        }
    tt, tt_truth = _tiktok_dataset(all_entries, random.Random(f"{seed}-tt"))
    datasets["tiktok-handle-sama.json"] = tt
    planted = [e for e in all_entries if e.truth["group"] == "coordinated-planted"]
    truth = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "synthetic": True,
        "notice": (
            "Kunci jawaban data sintetis untuk menguji indikator dan klasifikasi. "
            "Bukan observasi nyata dan bukan "
            "pernyataan tentang pihak mana pun."
        ),
        "accounts": {
            "organic_pro": ORGANIC_PRO,
            "organic_contra": ORGANIC_CONTRA,
            "askers_neutral": ASKERS,
            "personal_attackers": ATTACKERS,
            "planted_group_K": COORDINATED,
            "posters": POSTERS,
            "partial_coverage_only_target_1": PARTIAL_ONLY_T1,
        },
        "targets": truth_targets,
        "planted_pattern": {
            "description": (
                "Kelompok K membalas posting yang sama dalam jendela <= 90 detik, "
                "teks nyaris sama, "
                "tautan sama, "
                "me-repost posting yang sama, pada ketiga target. "
                "Hanya BAHAN UJI indikator CO-01..CO-06; "
                "ketiadaan ambang baku (ADR 0024)."
            ),
            "members_active": sorted({e.actor for e in planted}),
            "expected_indicators": ["CO-01", "CO-02", "CO-03", "CO-04", "CO-05", "CO-06"],
        },
        "hard_negatives": {
            "organic_burst": (
                "8 akun organik membalas dalam <= 8 menit pertama dengan teks berbeda "
                "(CO-02 tidak boleh bermakna)"
            ),
            "organic_shared_url": (
                "5 akun organik membagikan tautan populer yang sama pada target 2 (CO-05)"
            ),
            "same_stance_many_accounts": (
                "akun organik PRO/CONTRA bersikap sama tanpa pola waktu/teks bersama (AT-11)"
            ),
            "personal_attackers": "serangan personal independen, bukan koordinasi",
        },
        "cross_platform": tt_truth,
        "profile_coverage": {
            "account": PARTIAL_ONLY_T1,
            "observed_in_targets": [1],
            "expectation": (
                "profil menyatakan cakupan sebagian, bukan seluruh aktivitas akun (AT-17)"
            ),
        },
    }
    return Bundle(datasets, truth, {"entries": all_entries})


def write(out_dir: Path, seed: int = DEFAULT_SEED) -> Bundle:
    bundle = generate(seed)
    datasets = out_dir / "datasets"
    datasets.mkdir(parents=True, exist_ok=True)
    for name, data in bundle.datasets.items():
        (datasets / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (out_dir / "ground-truth.json").write_text(
        json.dumps(bundle.ground_truth, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return bundle
