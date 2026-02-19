"""Integration tests for cookie-overlay handling in WebsiteCaptureService."""

import io

import pytest
from PIL import Image

from app.infrastructure.capture.website_capture_service import CapturedPage
from app.infrastructure.capture.website_capture_service import WebsiteCaptureService
from tests.integration.services.cookie_test_service import run_cookie_test_service


def _pixel_at_top_left(image_bytes: bytes) -> tuple[int, int, int]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return image.getpixel((20, 20))


def _is_dark_overlay_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r < 55 and g < 55 and b < 55


async def _capture(service: WebsiteCaptureService, url: str) -> CapturedPage:
    return await service.capture_screenshot(url)


@pytest.mark.asyncio
async def test_capture_removes_iframe_cookie_overlay():
    with run_cookie_test_service() as base_url:
        capture = WebsiteCaptureService(viewport_width=1280, viewport_height=800, timeout_ms=20_000)
        await capture.start()
        try:
            captured = await _capture(capture, f"{base_url}/iframe-overlay.html")
        finally:
            await capture.stop()

    pixel = _pixel_at_top_left(captured.screenshot_bytes)
    assert not _is_dark_overlay_pixel(pixel), f"cookie overlay still visible in iframe fixture (pixel={pixel})"


@pytest.mark.asyncio
async def test_capture_removes_shadow_dom_cookie_overlay():
    with run_cookie_test_service() as base_url:
        capture = WebsiteCaptureService(viewport_width=1280, viewport_height=800, timeout_ms=20_000)
        await capture.start()
        try:
            captured = await _capture(capture, f"{base_url}/shadow-overlay.html")
        finally:
            await capture.stop()

    pixel = _pixel_at_top_left(captured.screenshot_bytes)
    assert not _is_dark_overlay_pixel(pixel), f"cookie overlay still visible in shadow DOM fixture (pixel={pixel})"


@pytest.mark.asyncio
async def test_capture_recovers_from_unintended_policy_navigation():
    with run_cookie_test_service() as base_url:
        capture = WebsiteCaptureService(viewport_width=1280, viewport_height=800, timeout_ms=20_000)
        await capture.start()
        try:
            captured = await _capture(capture, f"{base_url}/policy-redirect-root.html")
        finally:
            await capture.stop()

    pixel = _pixel_at_top_left(captured.screenshot_bytes)
    assert captured.title == "Policy Redirect Root Fixture"
    assert not _is_dark_overlay_pixel(pixel), (
        f"capture did not recover from unintended policy navigation (pixel={pixel}, title={captured.title!r})"
    )


@pytest.mark.asyncio
async def test_capture_keeps_explicit_policy_url_when_requested():
    with run_cookie_test_service() as base_url:
        capture = WebsiteCaptureService(viewport_width=1280, viewport_height=800, timeout_ms=20_000)
        await capture.start()
        try:
            captured = await _capture(capture, f"{base_url}/cookie-policy.html")
        finally:
            await capture.stop()

    pixel = _pixel_at_top_left(captured.screenshot_bytes)
    assert captured.title == "Cookie Policy Fixture"
    assert _is_dark_overlay_pixel(pixel), (
        f"explicit policy URL should not be auto-rewritten (pixel={pixel}, title={captured.title!r})"
    )
