/**
 * Teks petunjuk dalam aplikasi (PRD bagian 12, FR-004). Semua teks ada di satu berkas agar mudah
 * dipoles tanpa mengubah makna metodologi yang disepakati. Jangan menambah klaim di sini yang
 * tidak ada di PRD (mis. skor atau vonis buzzer).
 */
export const HELP = {
  createIssue: {
    title: "Issue dan proposition",
    body: 'Bedakan topik isu dari proposition yang dapat diuji. Issue adalah topik (misalnya "kebakaran hutan dan tanggung jawab korporasi") dan tidak diberi label pro/kontra. Pro/kontra dinilai terhadap proposition: klaim spesifik yang dapat disetujui atau ditentang, misalnya "perusahaan yang diduga terkait perlu diaudit". Satu issue boleh memiliki beberapa proposition.',
  },
  addProposition: {
    title: "Menulis proposition",
    body: "Tulis satu klaim spesifik. Isi proposition tidak dapat diubah setelah disimpan, karena penilaian respons akan merujuk pada isi yang sama.",
  },
  targetNote: {
    title: "Catatan konteks target",
    body: "Jelaskan interpretasi target: apa yang dinyatakan posting atau akun ini terhadap proposition, termasuk bila targetnya gambar atau video. Catatan ini adalah panduan interpretasi, bukan perintah. Jangan menulis instruksi agar semua kritik diberi label buzzer: sistem tidak memberi vonis buzzer, bot, atau akun bayaran. Setiap revisi menjadi versi baru dan versi lama tetap tersimpan.",
  },
  startInspection: {
    title: "Memulai inspeksi",
    body: "Inspeksi mengambil data yang tersedia dan diizinkan pada saat itu, bukan seluruh isi platform. Cakupan dan batas akses dicatat, dan hasilnya bisa parsial. Data yang kosong atau tidak terlihat tidak otomatis berarti objeknya tidak ada. Pemeriksaan berjalan di latar belakang dan statusnya diperbarui otomatis.",
  },
  reinspection: {
    title: "Inspeksi ulang",
    body: "Inspeksi ulang membuat pemeriksaan baru atas target yang sama; targetnya tidak dibuat ulang. Objek lama tidak digandakan, objek baru ditambahkan, dan perubahan ditinjau berdasarkan data baru. Objek yang tidak muncul pada satu pemeriksaan tidak dianggap terhapus.",
  },
  dataStates: {
    title: "Belum diperiksa, tidak ada data, gagal mengakses",
    body: "Tiga keadaan ini berbeda. Belum diperiksa: target belum pernah dicek, jadi belum ada data. Tidak ada data: pemeriksaan berhasil membaca target dan memang tidak menemukan balasan. Gagal mengakses data: pengambilan ditolak, gagal, atau belum didukung, sehingga TIDAK ada kesimpulan tentang isi target dan ini bukan berarti tidak ada balasan. Pada hasil parsial, objek yang tidak muncul tidak boleh dianggap dihapus.",
  },
  uncertaintyLabels: {
    title: "Label ketidakpastian",
    body: 'UNDETERMINED berarti belum dapat ditentukan, bukan netral. MIXED berarti posisinya campuran. Pilih UNDETERMINED bila ragu atau bila penilaian bergantung pada isi gambar/video yang tidak dianalisis sistem. Kesimpulan "belum cukup bukti" adalah hasil yang sah.',
  },
} as const;

export type HelpId = keyof typeof HELP;

/** Titik petunjuk yang wajib ada pada langkah yang sudah tersedia (FR-004). */
export const REQUIRED_HELP_IDS: readonly HelpId[] = [
  "createIssue",
  "targetNote",
  "startInspection",
  "reinspection",
  "dataStates",
  "uncertaintyLabels",
];
