"""Pesan ramah untuk status run (FR-095, NFR-08). SATU sumber kebenaran teks; UI hanya menampilkan.

Aturan:
- Pesan dibangun dari KODE terstruktur (status, LimitationCode, alasan tinjauan), bukan dari teks
  bebas adapter atau galat, sehingga tidak ada isi data/galat mentah yang bocor ke antarmuka.
- Kegagalan tidak pernah dinyatakan sebagai "tidak ada data"; ketidakpastian dijelaskan apa adanya.
- Teks boleh dipoles tim tanpa mengubah makna metodologi (PRD bagian 12); kode tetap stabil.
- Setiap anggota LimitationCode WAJIB punya teks (diuji): kode baru tanpa teks menggagalkan tes.
"""

from dataclasses import asdict, dataclass
from typing import Any

from collection.contracts import LimitationCode
from collection.models import InspectionRun, RunStatus

INFO, WARNING, ERROR = "info", "warning", "error"


@dataclass(frozen=True)
class Message:
    code: str
    level: str
    title: str
    detail: str
    action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LIMITATION_MESSAGES: dict[LimitationCode, Message] = {
    LimitationCode.ACCESS_RESTRICTED: Message(
        "access_restricted",
        ERROR,
        "Akses ditolak",
        "Platform menolak akses ke isi yang diminta (misalnya dibatasi atau meminta verifikasi). "
        "SNR tidak mencoba melewati pembatasan. Ini bukan berarti tidak ada balasan.",
        "Pastikan Anda memiliki jalur akses yang sah, lalu periksa lagi.",
    ),
    LimitationCode.AUTH_REQUIRED: Message(
        "auth_required",
        WARNING,
        "Sebagian isi memerlukan login",
        "Platform meminta login untuk menampilkan sisa isi. Hanya bagian yang terbuka yang "
        "terbaca; SNR tidak melewati tembok login.",
        "Jumlah balasan yang tampak dapat lebih sedikit dari kenyataan; perlakukan sebagai sampel.",
    ),
    LimitationCode.UNSUPPORTED: Message(
        "unsupported",
        ERROR,
        "Belum didukung",
        "Platform, jenis target, atau kemampuan yang diminta belum tersedia atau belum diuji pada "
        "pengambil data yang terpasang, sehingga tidak dijalankan.",
        "Gunakan jenis target atau platform yang didukung, atau hubungi tim pengembang.",
    ),
    LimitationCode.PARSE_FAILED: Message(
        "parse_failed",
        ERROR,
        "Struktur halaman tidak dikenali",
        "Pengambil data tidak dapat membaca halaman (tampilan platform mungkin berubah). "
        "Ini bukan berarti tidak ada balasan.",
        "Laporkan ke tim pengembang agar pengambil data diperbarui.",
    ),
    LimitationCode.TIMEOUT: Message(
        "timeout",
        ERROR,
        "Pemeriksaan melampaui batas waktu",
        "Halaman atau proses tidak selesai dalam batas waktu. Data yang sempat terbaca (bila ada) "
        "tidak lengkap.",
        "Coba periksa lagi nanti.",
    ),
    LimitationCode.NETWORK_ERROR: Message(
        "network_error",
        ERROR,
        "Platform tidak dapat dijangkau",
        "Terjadi gangguan jaringan atau platform mengembalikan galat server. Ini bukan berarti "
        "tidak ada balasan.",
        "Coba periksa lagi nanti.",
    ),
    LimitationCode.RATE_LIMITED: Message(
        "rate_limited",
        WARNING,
        "Dibatasi laju oleh platform",
        "Platform membatasi jumlah permintaan sehingga pengambilan dihentikan atau diperlambat.",
        "Tunggu beberapa saat sebelum memeriksa lagi.",
    ),
    LimitationCode.PAGINATION_INCOMPLETE: Message(
        "pagination_incomplete",
        WARNING,
        "Sebagian balasan tidak termuat",
        "Halaman lanjutan tidak berhasil dimuat. Balasan yang tampak hanya sebagian; objek yang "
        "tidak muncul tidak boleh dianggap dihapus.",
        "Periksa lagi untuk melengkapi data.",
    ),
    LimitationCode.COMPLETENESS_UNKNOWN: Message(
        "completeness_unknown",
        WARNING,
        "Kelengkapan data tidak dapat dipastikan",
        "Pengambil data tidak dapat memastikan seluruh balasan sudah terbaca.",
        "Perlakukan hasil sebagai sampel dan periksa lagi bila perlu.",
    ),
    LimitationCode.MAX_ITEMS_REACHED: Message(
        "max_items_reached",
        WARNING,
        "Dibatasi jumlah objek",
        "Pengambilan dihentikan karena batas jumlah objek tercapai; sisanya tidak terbaca.",
        "Perlakukan hasil sebagai sampel.",
    ),
    LimitationCode.TARGET_UNAVAILABLE: Message(
        "target_unavailable",
        ERROR,
        "Target tidak ditemukan atau tidak tersedia",
        "Platform menyatakan halaman target tidak ada atau tidak dapat dibuka. Ini bisa berarti "
        "dihapus, dibatasi, atau URL salah; SNR tidak dapat membedakannya.",
        "Periksa URL target, lalu coba lagi.",
    ),
    LimitationCode.ADAPTER_ERROR: Message(
        "adapter_error",
        ERROR,
        "Galat internal pada pengambil data",
        "Pengambil data mengalami galat tak terduga. Tidak ada kesimpulan tentang isi target yang "
        "dapat ditarik dari run ini.",
        "Laporkan ke tim pengembang.",
    ),
    LimitationCode.ARTIFACT_NOT_AVAILABLE: Message(
        "artifact_not_available",
        INFO,
        "Sebagian bukti visual tidak tersedia",
        "Tangkapan layar atau salinan halaman yang diminta tidak dapat dibuat. Data teks tidak "
        "terpengaruh.",
    ),
    LimitationCode.ARTIFACT_NOT_PERMITTED: Message(
        "artifact_not_permitted",
        INFO,
        "Penyimpanan sebagian bukti tidak diizinkan",
        "Jenis bukti tertentu tidak boleh disimpan untuk sumber ini. Data teks tidak terpengaruh.",
    ),
}

REVIEW_REASON_MESSAGES: dict[str, Message] = {
    "ingestion_failed_batches": Message(
        "review_ingestion_failed_batches",
        ERROR,
        "Sebagian data gagal disimpan",
        "Ada kelompok data yang gagal disimpan sehingga daftar respons tidak utuh.",
        "Periksa dengan tim pengembang sebelum memakai data run ini.",
    ),
    "ingestion_exception": Message(
        "review_ingestion_exception",
        ERROR,
        "Penyimpanan data terhenti karena galat",
        "Proses menyimpan hasil berhenti di tengah jalan; data run ini mungkin tidak utuh.",
        "Periksa dengan tim pengembang sebelum memakai data run ini.",
    ),
    "ingestion_timeout": Message(
        "review_ingestion_timeout",
        ERROR,
        "Penyimpanan data melampaui batas waktu",
        "Proses menyimpan hasil tidak selesai tepat waktu; data run ini mungkin tidak utuh.",
        "Periksa dengan tim pengembang sebelum memakai data run ini.",
    ),
    "artifact_persistence_problems": Message(
        "review_artifact_persistence_problems",
        WARNING,
        "Sebagian bukti gagal disimpan",
        "Beberapa artefak bukti tidak berhasil disimpan atau bentrok dengan arsip yang ada.",
        "Tinjau daftar artefak sebelum mengandalkan bukti run ini.",
    ),
    "artifacts_not_persisted": Message(
        "review_artifacts_not_persisted",
        WARNING,
        "Bukti tidak disimpan",
        "Hasil memuat artefak tetapi tidak ada yang tersimpan.",
        "Tinjau sebelum mengandalkan bukti run ini.",
    ),
    "mixed_source_methods": Message(
        "review_mixed_source_methods",
        WARNING,
        "Sumber data bercampur",
        "Run ini mencatat cara perolehan yang berbeda dari data sebelumnya pada run yang sama.",
        "Tinjau asal data sebelum membandingkan antarrun.",
    ),
}
_REVIEW_FALLBACK = Message(
    "review_other",
    WARNING,
    "Hasil perlu ditinjau",
    "Ada masalah pada penyimpanan data run ini yang perlu diperiksa manusia.",
    "Tinjau sebelum memakai data run ini.",
)

STATUS_MESSAGES: dict[str, Message] = {
    RunStatus.PENDING: Message(
        "run_pending",
        INFO,
        "Menunggu giliran",
        "Pemeriksaan sudah diminta dan menunggu dijalankan.",
    ),
    RunStatus.RUNNING: Message(
        "run_running",
        INFO,
        "Sedang diperiksa",
        "Pemeriksaan sedang berjalan; halaman akan diperbarui.",
    ),
    RunStatus.COMPLETED: Message(
        "run_completed",
        INFO,
        "Pemeriksaan selesai",
        "Selesai berarti cakupan yang diminta sudah terbaca; bukan jaminan seluruh konten platform "
        "ditemukan. Objek yang tidak muncul pada pemeriksaan berikutnya tidak otomatis dihapus.",
    ),
    RunStatus.PARTIAL: Message(
        "run_partial",
        WARNING,
        "Pengambilan parsial",
        "Hanya sebagian data yang berhasil dibaca. Jumlah yang tampak dapat lebih sedikit dari "
        "kenyataan dan objek yang tidak muncul tidak boleh dianggap dihapus.",
        "Periksa lagi untuk melengkapi data.",
    ),
    RunStatus.REVIEW_REQUIRED: Message(
        "run_review_required",
        WARNING,
        "Perlu ditinjau",
        "Run ini selesai tetapi ada masalah yang harus diperiksa manusia sebelum datanya dipakai.",
        "Tinjau alasan di bawah, lalu akui tinjauan.",
    ),
}
_FAILURE_FALLBACK = Message(
    "run_failed_unspecified",
    ERROR,
    "Pemeriksaan gagal",
    "Pemeriksaan tidak berhasil dan tidak ada alasan terstruktur yang tercatat.",
    "Periksa lagi atau hubungi tim pengembang.",
)

CONTEXT_INSUFFICIENT = Message(
    "context_insufficient",
    INFO,
    "Konteks target belum diisi",
    "Catatan konteks dan posisi awal terhadap proposition masih kosong. Pemeriksaan tetap dapat "
    "dijalankan, tetapi analisis nanti akan membatasi diri tanpa konteks yang cukup.",
    "Isi catatan konteks tanpa memerintahkan label tertentu terhadap kritik.",
)
NO_REPLIES = Message(
    "no_replies_observed",
    INFO,
    "Tidak ada balasan teramati",
    "Pemeriksaan berhasil membaca target dan tidak menemukan balasan pada cakupan yang diminta.",
)
RECONCILIATION_MESSAGES: dict[str, Message] = {
    "ERROR": Message(
        "reconciliation_error",
        WARNING,
        "Perbandingan antar-pemeriksaan gagal",
        "Data run ini tersimpan, tetapi status NEW/UNCHANGED/MODIFIED/NOT_OBSERVED belum tersedia.",
        "Hubungi tim pengembang; perbandingan dapat dijalankan ulang.",
    ),
    "BLOCKED": Message(
        "reconciliation_blocked",
        WARNING,
        "Perbandingan antar-pemeriksaan ditunda",
        "Perbandingan tidak dijalankan karena data run ini atau run pembandingnya belum utuh.",
        "Tinjau masalah penyimpanan data pada run terkait.",
    ),
}
RECONCILIATION_PENDING = Message(
    "reconciliation_pending",
    INFO,
    "Perbandingan belum dijalankan",
    "Status perubahan antar-pemeriksaan belum tersedia untuk run ini.",
)
INGESTION_INTERRUPTED = Message(
    "ingestion_interrupted",
    ERROR,
    "Penyimpanan data terputus",
    "Proses menyimpan hasil tidak pernah selesai; data run ini mungkin tidak utuh.",
    "Jangan memakai data run ini; periksa lagi.",
)
ARTIFACTS_REJECTED = Message(
    "artifacts_rejected",
    INFO,
    "Sebagian artefak tidak disimpan",
    "Artefak yang tampak memuat kredensial atau rahasia sengaja tidak disimpan (PRD bagian 13). "
    "Data teks tidak terpengaruh.",
)
COUNT_MISMATCH = Message(
    "count_mismatch",
    INFO,
    "Jumlah ditampilkan platform berbeda dari jumlah teramati",
    "Platform menampilkan satu angka dan SNR menghitung objek unik yang benar-benar terbaca; "
    "keduanya tidak harus sama (mis. balasan tersembunyi, dihapus, atau belum termuat).",
)


def _limitation_messages(limitations: list[dict[str, Any]]) -> list[Message]:
    out: list[Message] = []
    seen: set[str] = set()
    for item in limitations or []:
        try:
            code = LimitationCode(str(item.get("code")))
        except ValueError:
            continue
        if code.value not in seen:
            seen.add(code.value)
            out.append(LIMITATION_MESSAGES[code])
    return out


def run_messages(run: InspectionRun) -> list[Message]:
    """Pesan untuk satu run, urut dari paling penting. Hanya memakai kode terstruktur."""
    status = run.status
    coverage = run.coverage or {}
    messages: list[Message] = []

    if status in STATUS_MESSAGES:
        messages.append(STATUS_MESSAGES[status])

    limitation_msgs = _limitation_messages(run.limitations)
    if status == RunStatus.REVIEW_REQUIRED and run.review:
        for reason in run.review.get("reasons", []):
            messages.append(REVIEW_REASON_MESSAGES.get(reason, _REVIEW_FALLBACK))
    messages.extend(limitation_msgs)
    if status in (RunStatus.ACCESS_RESTRICTED, RunStatus.FAILED, RunStatus.UNSUPPORTED) and not (
        limitation_msgs
    ):
        messages.append(_FAILURE_FALLBACK)

    if status in (RunStatus.COMPLETED, RunStatus.PARTIAL, RunStatus.REVIEW_REQUIRED):
        observed = coverage.get("observed_reply_count")
        displayed = coverage.get("platform_displayed_count")
        if status == RunStatus.COMPLETED and observed == 0:
            messages.append(NO_REPLIES)
        elif displayed is not None and observed is not None and displayed != observed:
            messages.append(COUNT_MISMATCH)

    ingestion = run.ingestion or {}
    if ingestion.get("state") == "IN_PROGRESS" and status not in (
        RunStatus.PENDING,
        RunStatus.RUNNING,
    ):
        messages.append(INGESTION_INTERRUPTED)

    reconciliation = run.reconciliation
    if reconciliation is None:
        if status in (RunStatus.COMPLETED, RunStatus.PARTIAL):
            messages.append(RECONCILIATION_PENDING)
    elif reconciliation.get("state") in RECONCILIATION_MESSAGES:
        messages.append(RECONCILIATION_MESSAGES[reconciliation["state"]])

    report = (run.preservation or {}).get("report") or {}
    if report.get("rejected"):
        messages.append(ARTIFACTS_REJECTED)

    return messages


VERIFICATION_MESSAGES: dict[str, Message] = {
    "MATCH": Message(
        "verification_match",
        INFO,
        "Hash cocok",
        "Berkas yang tersimpan masih sama dengan saat disimpan (hash dan ukuran dihitung ulang dan "
        "sama dengan catatan).",
    ),
    "MISMATCH": Message(
        "verification_mismatch",
        ERROR,
        "Berkas berbeda dari saat disimpan",
        "Hash atau ukuran yang dihitung ulang tidak sama dengan catatan. Berkas ini tidak boleh "
        "dipakai sebagai bukti sampai penyebabnya dijelaskan. Kejadian ini tercatat permanen.",
        "Laporkan ke administrator; periksa cadangan dan akses ke penyimpanan bukti.",
    ),
    "MISSING": Message(
        "verification_missing",
        ERROR,
        "Berkas bukti tidak ditemukan",
        "Catatan artefak ada, tetapi berkasnya tidak ada di penyimpanan bukti. Kejadian ini "
        "tercatat permanen.",
        "Laporkan ke administrator; pulihkan dari cadangan bila tersedia.",
    ),
    "UNREADABLE": Message(
        "verification_unreadable",
        ERROR,
        "Berkas bukti tidak dapat diverifikasi",
        "Berkas tidak dapat dibaca secara aman (jalur tidak sah, symlink, atau galat baca). "
        "Hasilnya tidak dapat dipastikan. Kejadian ini tercatat permanen.",
        "Laporkan ke administrator.",
    ),
}
MANIFEST_MESSAGES: dict[str, Message] = {
    "CONSISTENT": Message(
        "manifest_consistent",
        INFO,
        "Manifest konsisten",
        "Daftar artefak di manifest sama dengan catatan artefak run ini (hash dan ukuran).",
    ),
    "ABSENT": Message(
        "manifest_absent",
        WARNING,
        "Tidak ada manifest",
        "Run ini tidak memiliki manifest tersimpan, sehingga daftar artefak tidak dapat "
        "dibandingkan dengan sumber kedua.",
    ),
    "INCONSISTENT": Message(
        "manifest_inconsistent",
        ERROR,
        "Manifest tidak sesuai dengan catatan artefak",
        "Daftar di manifest berbeda dari catatan artefak di basis data. Salah satunya tidak utuh.",
        "Laporkan ke administrator.",
    ),
    "UNTRUSTED": Message(
        "manifest_untrusted",
        ERROR,
        "Manifest tidak dapat dipercaya",
        "Manifest sendiri tidak lolos verifikasi hash atau tidak dapat dibaca, sehingga isinya "
        "tidak dipakai sebagai pembanding.",
        "Laporkan ke administrator.",
    ),
}
INTEGRITY_STATEMENT = (
    "Hash memeriksa apakah berkas yang tersimpan masih sama dengan saat di-hash. Hash tidak "
    "membuktikan bahwa konten platform autentik, lengkap, atau benar secara faktual."
)
