"""WP-0.4: normalisasi URL target (FR-011). Fungsi murni, tanpa database."""

import pytest
from investigations.enums import Platform
from investigations.errors import InvalidTargetURL
from investigations.target_urls import normalize_target_url


@pytest.mark.parametrize(
    ("platform", "raw", "expected"),
    [
        # Penulisan berbeda dari URL yang sama menjadi satu bentuk kanonik.
        (Platform.X, "https://x.com/user/status/123", "https://x.com/user/status/123"),
        (Platform.X, "HTTP://WWW.X.COM/user/status/123/", "https://x.com/user/status/123"),
        (Platform.X, "https://twitter.com/user/status/123", "https://x.com/user/status/123"),
        (Platform.X, "https://mobile.twitter.com/user/status/123?s=20&t=abc", "https://x.com/user/status/123"),
        (Platform.THREADS, "https://www.threads.net/@u/post/AbC", "https://threads.com/@u/post/AbC"),
        (Platform.INSTAGRAM, "https://instagram.com/p/XYZ/?igsh=abc&utm_source=x", "https://instagram.com/p/XYZ"),
        (Platform.TIKTOK, "https://www.tiktok.com/@u/video/9?lang=id&utm_medium=s", "https://tiktok.com/@u/video/9?lang=id"),
        (Platform.FACEBOOK, "https://m.facebook.com/story.php?story_fbid=1&id=2&fbclid=z", "https://facebook.com/story.php?id=2&story_fbid=1"),
        # Fragmen dibuang, slash ganda dirapikan, port standar dibuang.
        (Platform.X, "https://x.com:443//user//status/1#bagian", "https://x.com/user/status/1"),
        # Subdomain tautan pendek dipertahankan (diselesaikan adapter, bukan di sini).
        (Platform.TIKTOK, "https://vt.tiktok.com/ZSabc/", "https://vt.tiktok.com/ZSabc"),
    ],
)
def test_normalization(platform: str, raw: str, expected: str) -> None:
    assert normalize_target_url(platform, raw) == expected


def test_parameter_that_identifies_content_is_kept() -> None:
    url = "https://facebook.com/watch/?v=123456"
    assert normalize_target_url(Platform.FACEBOOK, url) == "https://facebook.com/watch?v=123456"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "x.com/user/status/1",  # tanpa skema
        "javascript:alert(1)",
        "ftp://x.com/user",
        "file:///etc/passwd",
        "https://user:pass@x.com/a",  # kredensial di URL
        "https://x.com:8080/a",  # port non-standar
        "https:///path-saja",
        "https://" + "a" * 2100 + ".x.com/",
    ],
)
def test_invalid_urls_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidTargetURL):
        normalize_target_url(Platform.X, raw)


@pytest.mark.parametrize(
    ("platform", "raw"),
    [
        (Platform.X, "https://tiktok.com/@u/video/1"),  # domain bukan milik platform terpilih
        (Platform.TIKTOK, "https://x.com/u/status/1"),
        (Platform.FACEBOOK, "https://evilfacebook.com/post/1"),  # bukan subdomain sah
        (Platform.X, "https://x.com.evil.example/u/status/1"),  # pengelabuan sufiks
        (Platform.INSTAGRAM, "https://example.com/p/1"),
    ],
)
def test_domain_must_match_platform(platform: str, raw: str) -> None:
    with pytest.raises(InvalidTargetURL):
        normalize_target_url(platform, raw)


def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(InvalidTargetURL):
        normalize_target_url("myspace", "https://x.com/a")
