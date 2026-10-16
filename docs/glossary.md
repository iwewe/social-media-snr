# Glosarium SNR

Sumber: PRD bagian 5. Jika berbeda dengan PRD, PRD yang berlaku.

| Istilah | Definisi operasional |
|---|---|
| Investigation | Wadah aktivitas pemeriksaan dan analisis atas satu ruang masalah. |
| Issue | Topik yang diteliti. |
| Proposition | Klaim spesifik yang menjadi acuan klasifikasi pro/kontra. Satu issue dapat memiliki lebih dari satu proposition. |
| Target | URL posting atau akun yang sengaja dipilih pengguna untuk diperiksa. |
| Seed post | Posting yang menjadi titik masuk jaringan percakapan. |
| ActorAccount | Identitas satu akun **pada satu platform**. Tidak disamakan dengan orang tertentu. |
| Post | Objek publikasi pada platform, termasuk video/post/Reel sesuai jenis asli. |
| Response | Reply atau comment terkait suatu target/post; jenis asli dan parent dipertahankan. |
| InspectionRun | Satu pelaksanaan pemeriksaan pada target yang sudah didaftarkan. |
| Observation | Kondisi objek yang berhasil diamati pada pemeriksaan tertentu. |
| EvidenceArtifact | Berkas preservasi dan metadata integritas/provenance-nya. |
| AnalysisRun | Pemrosesan terhadap versi dataset, versi konteks, dan parameter tertentu. |
| Finding | Hasil analisis yang telah ditinjau; berbeda dari observasi dan klasifikasi mesin. |

## Aturan identitas

- Post unik pada `(platform, external_post_id)`; akun unik pada `(platform, external_actor_id)`.
- Username, nama tampilan, dan URL **bukan** identitas utama.
- Tidak ada identitas, graf, atau analisis lintas platform.
- Sumber tanpa ID stabil: tandai kebutuhan verifikasi identitas, jangan gabungkan otomatis.

## Larangan istilah

SNR tidak mengeluarkan vonis "buzzer", "bot", "akun bayaran", atau "operator kampanye", dan tidak
memiliki skor untuk itu (PRD bagian 1 dan FR-079).
