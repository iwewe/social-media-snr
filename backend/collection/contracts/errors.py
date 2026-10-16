class ContractViolation(ValueError):
    """Data atau perilaku melanggar kontrak observasi/adapter (WP-1.1).

    Dilempar saat objek kontrak dibangun dengan isi yang tidak sah, agar pelanggaran tidak pernah
    sampai ke penyimpanan. Pesan ditulis untuk pengembang adapter, bukan pengguna akhir.
    """
