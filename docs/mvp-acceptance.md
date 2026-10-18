# Bukti kesiapan MVP fungsional (PRD bagian 20; rencana bagian 12)

Dokumen ini memetakan tiap butir definisi selesai ke bukti yang dapat diperiksa. **Menyatakan MVP "terbukti"
adalah keputusan tim/organisasi**; dokumen ini hanya menyajikan buktinya. Kelulusan fungsional MVP tidak sama dengan
kelulusan konektor platform (I3) maupun validasi ilmiah pada data nyata (I4): keduanya dilaporkan terpisah dan
**belum** terpenuhi (lihat bagian akhir).

Demonstrasi langsung: `make demo` menyiapkan database terpisah berisi data sintetis lengkap (3 target x 4 putaran,
M2-M5, satu koreksi klasifikasi, satu temuan disahkan) beserta akun acak; buka lewat tunnel SSH. Seluruh data fiktif.

| # | Butir PRD bagian 20 | Bukti otomatis | Peragaan |
|---|---|---|---|
| 1 | Login; buat investigation, issue, proposition, target, catatan konteks | `tests/test_investigations.py`, `tests/test_auth.py`, `tests/test_api.py`; E2E `tests/e2e/workspace_flow.py` (AT-07 bagian data) | Halaman Investigasi |
| 2 | Pemeriksaan lewat adapter uji/browser; observasi dan preservasi lokal berhash valid | `tests/test_artifact_persistence.py`, `tests/test_preservation_storage.py`, `tests/browser/test_browser_orchestrator.py` (halaman simulasi), E2E `inspection_flow.py` (AT-06, AT-18) | Tombol Inspect; halaman bukti run; Verifikasi hash |
| 3 | Pemeriksaan ulang tanpa duplikasi; riwayat lama utuh | `tests/test_reconciliation.py`, `tests/test_ingestion.py`, `tests/test_synthetic_dataset.py` (AT-01..05) | Riwayat run per target; kolom Perubahan |
| 4 | Penilaian stance/karakter yang dapat direview; penelusuran ke parent dan bukti | `tests/test_m2_rules.py`, `tests/test_m2_assessment.py`, `tests/test_api_analysis.py` (AT-08..10, AT-16), `tests/test_audit.py`, E2E `analysis_flow.py` | Tab Respons (Tinjau); laci Jejak bukti; tab Jejak audit |
| 5 | Actor-Issue Profile dengan batas cakupan | `tests/test_m3_profile.py`, `tests/test_m3_run.py` (AT-17), `test_api_analysis.py` (pernyataan cakupan di atas) | Tab Profil akun |
| 6 | Graf relasi dan indikator pola yang dibedakan dari observasi langsung | `tests/test_m4_network.py`, `tests/test_m4_run.py`, `tests/test_co_indicators.py`, `tests/test_co_run.py`, `test_api_analysis.py::test_AT12_*` (AT-11..13) | Tab Jaringan: garis penuh berpanah (interaksi) vs putus-putus (kemiripan perilaku) + legenda |
| 7 | Kasus ambigu, akses gagal, data parsial, isolasi identitas lintas platform | `tests/test_synthetic_dataset.py` (kasus tepi, AT-13), `tests/test_orchestrator.py`, `tests/contracts/` (AT-14), `tests/test_run_messages.py` | Run parsial/akses ditolak pada riwayat; pesan status |
| 8 | Tidak ada vonis otomatis buzzer dan tidak ada analisis semantik isi video/gambar | `tests/architecture/` (larangan identifier buzzer/bot-score/koordinasi-skor di backend dan frontend), `tests/test_m5_policy.py` (larangan istilah vonis pada temuan), `frontend/src/pages/AnalysisPage.test.tsx` (tidak ada UI skor/peringkat), M2 menandai gambar/video sebagai UNDETERMINED (tidak dianalisis) | Coba menulis temuan dengan istilah vonis: ditolak server |

Ringkasan AT: AT-01..AT-18 punya tes otomatis (pemetaan lengkap pada `rencana-implementasi-snr.md` bagian 9).
Tingkat verifikasi: tes unit/integrasi/E2E dijalankan `make ci` dan `make e2e`; kode kritis diuji mutasi sengaja
(`tests/mutation_specs/`, `docs/verification.md`).

## Yang BELUM terpenuhi (dilaporkan terpisah, bukan bagian kelulusan MVP fungsional)

- **I3 konektor platform:** seluruh pengambilan otomatis `DISABLED` menunggu keputusan organisasi dan akses yang sah
  (`docs/adapters/`, ADR 0036). Hanya impor dataset yang sah dan adapter simulasi yang berfungsi.
- **I4 pilot:** belum dilaksanakan; membutuhkan target nyata yang sah, izin tertulis, dan penilai manusia
  (`docs/pilot/`, ADR 0037). Tidak ada klaim kualitas model/koordinasi pada data nyata; hasil sintetis hanya menguji alur.
- **Keputusan terbuka rencana bagian 11:** D-01 (model NLP), D-04 (durasi retensi), D-05 (kapasitas/perangkat backup),
  D-06 (batas waktu job), D-08 (desain laporan) tetap terbuka; D-02/D-07 hanya dieksplorasi pada data sintetis.
- **Keterbatasan produk yang diketahui:** analisis dipicu operator (`manage.py run_analyses`), belum dari antarmuka;
  tidak ada enkripsi backup, penjadwalan backup otomatis, maupun domain/sertifikat produksi (ADR 0034/0035);
  keamanan operasional VM (kata sandi SSH, kredensial di deskripsi VM Proxmox) adalah tindakan di luar repo.
