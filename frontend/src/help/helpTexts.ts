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
  viewResponses: {
    title: "Melihat respons mentah",
    body: "Daftar ini adalah data mentah yang teramati pada satu pemeriksaan; belum ada klasifikasi, stance, atau skor. Penulis dikenali dari ID akun, bukan dari username atau nama tampilan yang dapat berubah. Kolom Perubahan membandingkan dengan pemeriksaan sebelumnya: objek yang tidak muncul ditandai tidak teramati kali ini, bukan dihapus. Stance terhadap isu dinilai terhadap proposition, dan itu berbeda dari kesepakatan terhadap posting yang dibalas.",
  },
  teamRoles: {
    title: "Peran dalam tim",
    body: "Setiap investigasi punya tim. Pemilik mengelola anggota dan melakukan semua yang dapat dilakukan Anggota. Anggota menulis issue, proposition, target, dan konteks, menjalankan inspeksi, dan mengakui tinjauan. Pembaca hanya membaca, termasuk bukti dan verifikasi hash. Orang yang bukan anggota tidak melihat investigasi itu sama sekali. Super admin melihat semuanya. Mencabut akses tidak menghapus riwayat siapa pernah menjadi anggota.",
  },
  dataStates: {
    title: "Belum diperiksa, tidak ada data, gagal mengakses",
    body: "Tiga keadaan ini berbeda. Belum diperiksa: target belum pernah dicek, jadi belum ada data. Tidak ada data: pemeriksaan berhasil membaca target dan memang tidak menemukan balasan. Gagal mengakses data: pengambilan ditolak, gagal, atau belum didukung, sehingga TIDAK ada kesimpulan tentang isi target dan ini bukan berarti tidak ada balasan. Pada hasil parsial, objek yang tidak muncul tidak boleh dianggap dihapus.",
  },
  uncertaintyLabels: {
    title: "Label ketidakpastian",
    body: 'UNDETERMINED berarti belum dapat ditentukan, bukan netral. MIXED berarti posisinya campuran. Pilih UNDETERMINED bila ragu atau bila penilaian bergantung pada isi gambar/video yang tidak dianalisis sistem. Kesimpulan "belum cukup bukti" adalah hasil yang sah.',
  },
  viewClassifiedResponses: {
    title: "Respons terklasifikasi",
    body: "Setiap respons ditandai kategorinya: fakta observasi (data yang diambil apa adanya), hasil mesin (klasifikasi otomatis dari aturan), atau ditinjau manusia (koreksi peninjau yang menjadi baris baru, bukan menimpa). Stance dinilai terhadap proposition dan berbeda dari kesepakatan terhadap posting yang dibalas. Klasifikasi mesin dapat keliru; respons yang ditandai perlu tinjauan sebaiknya diperiksa manusia, dan semua koreksi tersimpan dengan riwayatnya.",
  },
  viewActorProfile: {
    title: "Profil akun terhadap isu",
    body: "Profil ini meringkas apa yang terobservasi dari satu akun pada isu ini, per dimensi, dengan pernyataan cakupan di bagian atas: berapa banyak data yang tersedia dan apa yang tidak terlihat. Dimensi tanpa data cukup ditandai data belum cukup, bukan nol. Profil bukan penilaian niat atau identitas akun, dan tidak memberi vonis tentang siapa yang berada di balik akun.",
  },
  viewNetwork: {
    title: "Jaringan dan indikator pola",
    body: "Garis penuh berpanah adalah interaksi yang tercatat (balasan, kutipan, dan sejenisnya). Garis putus-putus tanpa panah adalah kemiripan perilaku yang dihitung, dan BUKAN bukti hubungan atau koordinasi antar akun. Setiap indikator disertai pembanding acak dan penjelasannya; pola yang sama dapat muncul secara wajar, misalnya karena topik yang sedang ramai. Komunitas hasil algoritma dapat berubah antar-jalankan, dan hasil jaringan hanya bahan untuk ditinjau manusia.",
  },
  viewFindings: {
    title: "Temuan",
    body: "Temuan adalah pernyataan pola yang terobservasi, ditulis dan disahkan peninjau manusia. Setiap temuan memuat confidence beserta alasannya (bukan probabilitas), kualitas bukti pada empat sumbu terpisah, dan pertimbangan semua hipotesis alternatif. Temuan tidak menyatakan adanya operasi berbayar atau pengendali akun. Revisi membuat versi baru; versi lama tetap tersimpan. Data sintetis hanya menguji alur dan membatasi confidence.",
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
  "teamRoles",
  "viewResponses",
  "uncertaintyLabels",
  "viewClassifiedResponses",
  "viewActorProfile",
  "viewNetwork",
  "viewFindings",
];
