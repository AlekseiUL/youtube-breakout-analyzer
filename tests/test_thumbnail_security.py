from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
import urllib.request

import pytest

from youtube_breakout import yt_thumbnails


PNG_BYTES = b"\x89PNG\r\n\x1a\nfixture"
JPEG_BYTES = b"\xff\xd8fixture"


class FakeResponse:
    def __init__(self, body: bytes, content_type: str, url: str = "https://i.ytimg.com/vi/abc/hqdefault.jpg") -> None:
        self._body = BytesIO(body)
        self.headers = {"Content-Type": content_type}
        self.url = url

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def open(self, req: urllib.request.Request, timeout: float) -> FakeResponse:
        return self.response


@pytest.mark.parametrize(
    "url",
    [
        "http://i.ytimg.com/vi/abc/hqdefault.jpg",
        "https://example.com/vi/abc/hqdefault.jpg",
        "https://user:pass@i.ytimg.com/vi/abc/hqdefault.jpg",
    ],
)
def test_thumbnail_url_policy_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(yt_thumbnails.ThumbnailDownloadError) as excinfo:
        yt_thumbnails.validate_thumbnail_url(url)
    assert excinfo.value.code == "unsafe_thumbnail_url"


def test_thumbnail_redirect_handler_rejects_unsafe_redirect_target() -> None:
    handler = yt_thumbnails.ValidatingRedirectHandler()
    req = urllib.request.Request("https://i.ytimg.com/vi/abc/hqdefault.jpg")
    with pytest.raises(yt_thumbnails.ThumbnailDownloadError) as excinfo:
        handler.redirect_request(req, None, 302, "Found", {}, "https://example.com/not-youtube.jpg")
    assert excinfo.value.code == "unsafe_redirect_url"


def test_thumbnail_download_accepts_valid_youtube_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        yt_thumbnails,
        "build_thumbnail_opener",
        lambda: FakeOpener(FakeResponse(PNG_BYTES, "image/png")),
    )
    target = tmp_path / "thumb.png"
    meta = yt_thumbnails.download_thumbnail("https://i.ytimg.com/vi/abc/hqdefault.jpg", target, timeout_sec=1)
    assert target.read_bytes() == PNG_BYTES
    assert meta["content_type"] == "image/png"
    assert meta["bytes"] == len(PNG_BYTES)


def test_thumbnail_download_rejects_unsafe_final_redirect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        yt_thumbnails,
        "build_thumbnail_opener",
        lambda: FakeOpener(FakeResponse(PNG_BYTES, "image/png", url="https://example.com/final.png")),
    )
    with pytest.raises(yt_thumbnails.ThumbnailDownloadError) as excinfo:
        yt_thumbnails.download_thumbnail("https://i.ytimg.com/vi/abc/hqdefault.jpg", tmp_path / "thumb.png", timeout_sec=1)
    assert excinfo.value.code == "unsafe_redirect_url"


def test_thumbnail_download_rejects_oversized_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        yt_thumbnails,
        "build_thumbnail_opener",
        lambda: FakeOpener(FakeResponse(JPEG_BYTES + b"x" * 32, "image/jpeg")),
    )
    with pytest.raises(yt_thumbnails.ThumbnailDownloadError) as excinfo:
        yt_thumbnails.download_thumbnail(
            "https://i.ytimg.com/vi/abc/hqdefault.jpg",
            tmp_path / "thumb.jpg",
            timeout_sec=1,
            max_bytes=4,
        )
    assert excinfo.value.code == "thumbnail_too_large"


def test_thumbnail_download_rejects_non_image_content_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        yt_thumbnails,
        "build_thumbnail_opener",
        lambda: FakeOpener(FakeResponse(PNG_BYTES, "text/html")),
    )
    with pytest.raises(yt_thumbnails.ThumbnailDownloadError) as excinfo:
        yt_thumbnails.download_thumbnail("https://i.ytimg.com/vi/abc/hqdefault.jpg", tmp_path / "thumb.png", timeout_sec=1)
    assert excinfo.value.code == "invalid_content_type"


def test_thumbnail_download_rejects_invalid_image_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        yt_thumbnails,
        "build_thumbnail_opener",
        lambda: FakeOpener(FakeResponse(b"not an image", "image/jpeg")),
    )
    with pytest.raises(yt_thumbnails.ThumbnailDownloadError) as excinfo:
        yt_thumbnails.download_thumbnail("https://i.ytimg.com/vi/abc/hqdefault.jpg", tmp_path / "thumb.jpg", timeout_sec=1)
    assert excinfo.value.code == "invalid_image_bytes"


def test_analyze_items_returns_deterministic_degraded_output_for_unsafe_url(tmp_path: Path) -> None:
    rows = yt_thumbnails.analyze_items(
        [{"video_id": "abc123", "title": "Unsafe", "thumbnail_url": "http://i.ytimg.com/vi/abc/hqdefault.jpg"}],
        tmp_path / "run",
        timeout_sec=1,
    )
    assert rows[0]["status"] == "degraded"
    assert rows[0]["error_code"] == "unsafe_thumbnail_url"
