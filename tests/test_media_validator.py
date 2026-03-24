"""
Tests for media_validator utility.
"""
from backend.utils.media_validator import validate_media, _is_safe_url


def test_safe_url_https():
    assert _is_safe_url("https://example.com/image.jpg") is True


def test_unsafe_url_http():
    assert _is_safe_url("http://example.com/image.jpg") is False


def test_unsafe_url_localhost():
    assert _is_safe_url("https://localhost/secret") is False


def test_unsafe_url_private_ip():
    assert _is_safe_url("https://192.168.1.1/data") is False


def test_unsafe_url_metadata():
    assert _is_safe_url("https://169.254.169.254/latest/meta-data") is False


def test_validate_media_no_warnings():
    warnings = validate_media(
        platform="instagram",
        media_type="image",
        media_urls=["https://cdn.example.com/photo.jpg"],
        caption="Hello!",
    )
    assert warnings == []


def test_validate_media_caption_too_long():
    warnings = validate_media(
        platform="twitter",
        media_type="image",
        media_urls=["https://cdn.example.com/photo.jpg"],
        caption="x" * 300,
    )
    assert any("caption too long" in w for w in warnings)


def test_validate_media_unsupported_format():
    warnings = validate_media(
        platform="instagram",
        media_type="image",
        media_urls=["https://cdn.example.com/photo.bmp"],
    )
    assert any("not supported" in w for w in warnings)


def test_validate_media_too_many_images():
    urls = [f"https://cdn.example.com/img{i}.jpg" for i in range(15)]
    warnings = validate_media(
        platform="instagram",
        media_type="carousel",
        media_urls=urls,
    )
    assert any("too many images" in w for w in warnings)


def test_validate_media_video_multiple_urls():
    warnings = validate_media(
        platform="tiktok",
        media_type="video",
        media_urls=["https://cdn.example.com/v1.mp4", "https://cdn.example.com/v2.mp4"],
    )
    assert any("only 1 video" in w for w in warnings)


def test_validate_media_no_urls():
    warnings = validate_media(
        platform="instagram",
        media_type="image",
        media_urls=[],
    )
    assert any("no media URLs" in w for w in warnings)


def test_validate_media_unsafe_url():
    warnings = validate_media(
        platform="facebook",
        media_type="image",
        media_urls=["http://example.com/img.jpg"],
    )
    assert any("Unsafe" in w for w in warnings)


def test_validate_media_file_size_too_large():
    warnings = validate_media(
        platform="twitter",
        media_type="image",
        media_urls=["https://cdn.example.com/big.jpg"],
        file_sizes_mb=[10.0],
    )
    assert any("too large" in w for w in warnings)


def test_validate_video_format_unsupported():
    warnings = validate_media(
        platform="instagram",
        media_type="video",
        media_urls=["https://cdn.example.com/clip.avi"],
    )
    assert any("not supported" in w for w in warnings)
