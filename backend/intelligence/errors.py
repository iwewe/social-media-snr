class AnalysisError(Exception):
    """Dasar galat analisis; pesan aman ditampilkan (tidak memuat isi data)."""


class InvalidSelection(AnalysisError):
    pass


class InvalidParameters(AnalysisError):
    pass


class UnknownMethod(AnalysisError):
    pass


class NothingNew(AnalysisError):
    """Analisis ulang tidak menemukan observasi baru dibanding dataset sebelumnya."""
