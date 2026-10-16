class DomainError(Exception):
    """Pelanggaran aturan domain; pesan aman ditampilkan ke pengguna."""


class InvalidTargetURL(DomainError):
    pass


class DuplicateTarget(DomainError):
    """URL target yang sama (setelah normalisasi) sudah terdaftar pada investigation ini."""

    def __init__(self, existing_id: int) -> None:
        super().__init__("Target dengan URL yang sama sudah terdaftar pada investigasi ini.")
        self.existing_id = existing_id


class InvalidContext(DomainError):
    pass
