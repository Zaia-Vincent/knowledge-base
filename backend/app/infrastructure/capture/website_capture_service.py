"""Website Capture Service — Playwright-based full-page screenshot capture.

Uses a headless Chromium browser to navigate to URLs, dismiss cookie banners,
scroll to trigger lazy-loading, and capture full-page PNG screenshots for
downstream LLM vision processing.

Aligned with the proven patterns from the Foundry PlaywrightScreenshotProvider.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Frame,
    Locator,
    Page,
    Playwright,
)

logger = logging.getLogger(__name__)

# ── Consent script URL patterns to block pre-navigation ─────────────
# Prevents cookie consent banners from ever being injected into the DOM.
_BLOCKED_CONSENT_SCRIPT_PATTERNS = [
    "*cookieyes.com*",
    "*cookiebot.com*",
    "*cdn.cookielaw.org*",
    "*onetrust.com*",
    "*didomi.io*",
    "*quantcast.com*",
    "*trustarc.com*",
    "*osano.com*",
    "*termly.io*",
    "*iubenda.com*",
    "*klaro.org*",
    "*complianz*cookie*",
    "*cookie-consent*.js*",
    "*cookie-notice*.js*",
    "*cookie-law*.js*",
    "*gdpr*consent*.js*",
    "*cookieconsent*.js*",
    "*cookie-script.com*",
    "*consentmanager.net*",
    "*usercentrics.eu*",
    "*privacy-center*.js*",
]

_COOKIE_KEYWORDS = (
    "cookie",
    "consent",
    "privacy",
    "gdpr",
    "tracking",
)

_CONSENT_HIDE_CSS = """
    [class*="cookie" i],
    [id*="cookie" i],
    [class*="consent" i],
    [id*="consent" i],
    [class*="gdpr" i],
    [id*="gdpr" i],
    [class*="privacy-banner" i],
    [id*="privacy-banner" i],
    #CybotCookiebotDialog,
    #onetrust-consent-sdk,
    .cc-window,
    .cc-banner,
    .qc-cmp-ui-container,
    .modal-backdrop {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
"""

_POLICY_PATH_TERMS = (
    "cookie-policy",
    "privacy-policy",
    "cookiebeleid",
    "privacybeleid",
)


@dataclass
class CapturedPage:
    """Result of capturing a web page."""

    url: str
    title: str
    screenshot_bytes: bytes
    captured_at: datetime


class WebsiteCaptureService:
    """Infrastructure service for capturing web page screenshots via Playwright.

    Lifecycle:
        - ``start()`` launches the browser (call once at app startup)
        - ``capture_screenshot()`` navigates and captures
        - ``stop()`` closes the browser (call on shutdown)
    """

    def __init__(
        self,
        viewport_width: int = 1280,
        viewport_height: int = 800,
        timeout_ms: int = 30_000,
    ) -> None:
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Launch the headless Chromium browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        logger.info(
            "WebsiteCaptureService started (viewport=%dx%d, timeout=%dms)",
            self._viewport_width,
            self._viewport_height,
            self._timeout_ms,
        )

    async def stop(self) -> None:
        """Close the browser and clean up Playwright resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("WebsiteCaptureService stopped")

    async def capture_screenshot(self, url: str) -> CapturedPage:
        """Navigate to a URL and capture a full-page screenshot.

        Pipeline:
            0. Block consent scripts via route interception
            1. Navigate with progressive fallback
            2. Handle cookie consent banners
            3. Scroll for lazy-loaded content
            4. Dismiss modal popups
            5. Expand accordions
            6. Wait for images
            7. Remove remaining cookie elements from DOM
            8. Take full-page PNG screenshot
        """
        if not self._browser:
            raise RuntimeError("WebsiteCaptureService not started — call start() first")

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        context: BrowserContext = await self._browser.new_context(
            viewport={"width": self._viewport_width, "height": self._viewport_height},
            service_workers="block",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
            ),
        )

        try:
            page = await context.new_page()
            page.set_default_timeout(self._timeout_ms)

            # Strategy 0: Block consent scripts before navigation
            await self._block_consent_scripts(context)

            # Navigate with progressive fallback
            logger.info("Capturing: %s", url)
            await self._navigate_with_fallback(page, url)

            # Wait for initial render
            await page.wait_for_timeout(500)

            # Try to wait for network idle (short timeout, don't fail)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.debug("Network idle timeout — proceeding with capture")

            # Handle cookie consent banners
            await self._handle_cookie_consent(page)
            await self._recover_if_unintended_policy_navigation(page, requested_url=url)

            # Scroll for lazy-loaded content
            await self._scroll_for_lazy_load(page)

            # Dismiss modal popups
            await self._dismiss_popups(page)

            # Expand accordions to reveal hidden content
            await self._expand_accordions(page)

            # Wait for all images to fully load
            await self._wait_for_images(page)

            # Re-run consent handling after lazy content/frame loads
            await self._handle_cookie_consent(page)
            await self._recover_if_unintended_policy_navigation(page, requested_url=url)

            # Final cookie cleanup: remove remaining elements from DOM
            await self._remove_cookie_dom_elements(page)
            await self._remove_cookie_text_elements(page)

            # Extra wait for JS animations to settle
            await page.wait_for_timeout(800)

            # Capture full-page screenshot
            screenshot = await page.screenshot(full_page=True, type="png")
            title = await page.title()

            logger.info(
                "Captured %s — title=%r, screenshot=%d bytes",
                url, title, len(screenshot),
            )

            return CapturedPage(
                url=url,
                title=title or url,
                screenshot_bytes=screenshot,
                captured_at=datetime.now(timezone.utc),
            )
        finally:
            await context.close()

    # ── Strategy 0: Route interception ───────────────────────────────

    async def _block_consent_scripts(self, context: BrowserContext) -> None:
        """Block known cookie consent scripts via route interception."""
        for pattern in _BLOCKED_CONSENT_SCRIPT_PATTERNS:
            try:
                async def _abort(route, _p=pattern):
                    logger.debug("Blocked consent script: %s (pattern=%s)", route.request.url[:120], _p)
                    await route.abort()
                await context.route(pattern, _abort)
            except Exception as e:
                logger.debug("Failed to register route block for %s: %s", pattern, e)

        logger.info("Registered %d consent script route blocks", len(_BLOCKED_CONSENT_SCRIPT_PATTERNS))

    # ── Navigation ──────────────────────────────────────────────────

    async def _navigate_with_fallback(self, page: Page, url: str) -> None:
        """Navigate with progressive fallback for resilient page loading."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        strategies = [
            ("networkidle", self._timeout_ms // 2),
            ("load", self._timeout_ms),
            ("domcontentloaded", self._timeout_ms),
        ]

        for wait_until, timeout in strategies:
            try:
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                if response and response.status >= 400:
                    logger.warning("HTTP %d for %s — continuing", response.status, url)
                logger.info("Navigation succeeded with strategy=%s", wait_until)
                return
            except PlaywrightTimeout:
                logger.warning("Navigation strategy=%s timed out — trying next", wait_until)
                continue

        raise TimeoutError(f"All navigation strategies failed for {url}")

    # ── Cookie consent handling (aligned with reference) ─────────────

    async def _handle_cookie_consent(self, page: Page) -> None:
        """Detect and accept cookie consent banners.

        Uses the same proven pattern as the Foundry PlaywrightScreenshotProvider:
        1. Try common CSS selectors via Playwright locator API
        2. Try text-based matching via get_by_role
        3. Fallback: hide remaining banners via CSS
        """
        logger.debug("Checking for cookie consent banners...")

        # Common button texts to accept cookies (multiple languages)
        accept_texts = [
            "Accept all cookies", "Accept cookies", "Accept all",
            "Allow all cookies", "Allow cookies", "I agree to cookies",
            "Akkoord", "Accepteren", "Alles accepteren",
            "Alle akzeptieren", "Akzeptieren",
            "Accepter tout", "Tout Accepter", "Tout accepter", "Accepter",
            "Aceptar todo", "Aceptar",
        ]

        # Common selectors for cookie consent frameworks
        common_selectors = [
            # Generic cookie-specific selectors
            'button[id*="cookie" i]',
            'button[id*="consent"]',
            'button[class*="cookie" i]',
            'button[class*="consent"]',
            'button[class*="gdpr" i]',
            '[data-action*="accept" i]',
            '[data-action*="consent" i]',
            # CookieBot
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            "#CybotCookiebotDialogBodyButtonAccept",
            # OneTrust
            "#onetrust-accept-btn-handler",
            ".onetrust-close-btn-handler",
            # Cookie Consent (Osano)
            ".cc-btn.cc-allow",
            ".cc-accept-all",
            # GDPR Cookie Consent
            '[data-testid="cookie-accept"]',
            '[data-action="accept"]',
            # Klaro
            ".cm-btn-accept-all",
            ".cm-btn-success",
            # Complianz
            ".cmplz-accept",
            "#cmplz-cookiebanner-container .cmplz-accept",
            # Borlabs Cookie
            "#BorlabsCookieBoxButtonAccept",
            # Quantcast/TCF
            '.qc-cmp-button[mode="primary"]',
            ".qc-cmp2-summary-buttons button:first-child",
            # CookieYes
            "[data-cky-tag='accept-button']",
            ".cky-btn-accept",
            # Usercentrics
            "[data-testid='uc-accept-all-button']",
            # Iubenda
            ".iubenda-cs-accept-btn",
            # Termly
            "[data-tid='banner-accept']",
            # Generic patterns
            '[aria-label*="accept" i]',
            '[aria-label*="agree" i]',
            '[aria-label*="consent" i]',
        ]

        clicked_any = False
        frames = self._iter_frames(page)

        # Strategy 1: Try common selectors first (locator API)
        for frame in frames:
            for selector in common_selectors:
                try:
                    button = frame.locator(selector).first
                    if not await button.is_visible(timeout=200):
                        continue
                    if not await self._looks_like_cookie_action(button):
                        continue
                    await button.click(timeout=1000)
                    logger.info("Clicked cookie consent button: %s (frame=%s)", selector, frame.url[:120])
                    clicked_any = True
                    await page.wait_for_timeout(150)
                except Exception:
                    continue

        # Strategy 2: Try text-based matching (get_by_role)
        if not clicked_any:
            for text in accept_texts:
                for frame in frames:
                    try:
                        button = frame.get_by_role("button", name=text, exact=False).first
                        if not await button.is_visible(timeout=200):
                            continue
                        if not await self._looks_like_cookie_action(button):
                            continue
                        await button.click(timeout=1000)
                        logger.info("Clicked cookie button with text: %s (frame=%s)", text, frame.url[:120])
                        clicked_any = True
                        await page.wait_for_timeout(150)
                    except Exception:
                        continue

        # Strategy 3: Hide common cookie banner containers via CSS
        if not clicked_any:
            for frame in frames:
                await self._inject_cookie_hide_css(frame)

        # Wait briefly for any animations
        await page.wait_for_timeout(300)

    # ── DOM removal of cookie elements ───────────────────────────────

    async def _remove_cookie_dom_elements(self, page: Page) -> None:
        """Remove known cookie/consent overlay containers from the DOM entirely."""
        for frame in self._iter_frames(page):
            try:
                removed = await frame.evaluate("""
                    () => {
                        const selectors = [
                            '#onetrust-banner-sdk', '#onetrust-consent-sdk',
                            '.onetrust-pc-dark-filter',
                            '#CybotCookiebotDialog', '#CybotCookiebotDialogBodyUnderlay',
                            '#didomi-host',
                            '.cky-consent-container', '.cky-overlay', '[class*="cky-consent" i]',
                            '#cmplz-cookiebanner-container', '.cmplz-cookiebanner',
                            '#iubenda-cs-banner', '.iubenda-cs-container',
                            '.osano-cm-window', '.osano-cm-dialog',
                            '[id*="termly" i]',
                            '.cc-window', '.cc-banner',
                            '.w-cookie-consent',
                            '[class*="cookie-banner" i]', '[class*="cookie-notice" i]',
                            '[class*="cookie-consent" i]', '[class*="cookie-popup" i]',
                            '[class*="cookie-wall" i]', '[class*="cookiewall" i]',
                            '[id*="cookie-banner" i]', '[id*="cookie-notice" i]',
                            '[id*="cookie-consent" i]', '[id*="cookiebar" i]',
                            '[class*="consent-banner" i]', '[class*="consent-overlay" i]',
                            '[class*="consent-wall" i]', '[class*="gdpr-banner" i]',
                            '[class*="privacy-banner" i]',
                            '.modal-backdrop',
                            '[class*="overlay" i][class*="cookie" i]',
                        ];
                        const keywords = ['cookie', 'consent', 'privacy', 'gdpr', 'tracking'];
                        const roots = [document];
                        for (let i = 0; i < roots.length; i++) {
                            const root = roots[i];
                            const hostElements = root.querySelectorAll('*');
                            for (const host of hostElements) {
                                if (host.shadowRoot) roots.push(host.shadowRoot);
                            }
                        }

                        const removed = new Set();
                        const tryRemove = (el) => {
                            if (!el || removed.has(el)) return;
                            removed.add(el);
                            el.remove();
                        };

                        // Remove known CMP selectors across document + open shadow roots.
                        for (const root of roots) {
                            for (const selector of selectors) {
                                for (const el of root.querySelectorAll(selector)) {
                                    tryRemove(el);
                                }
                            }
                        }

                        // Remove large fixed/sticky keyword overlays as generic fallback.
                        for (const root of roots) {
                            const candidates = root.querySelectorAll('div, section, aside, dialog, article, form');
                            for (const el of candidates) {
                                if (removed.has(el)) continue;
                                const style = getComputedStyle(el);
                                if (style.display === 'none' || style.visibility === 'hidden') continue;
                                if (style.position !== 'fixed' && style.position !== 'sticky') continue;
                                const rect = el.getBoundingClientRect();
                                if (rect.width < window.innerWidth * 0.5 || rect.height < window.innerHeight * 0.2) {
                                    continue;
                                }
                                const zIndex = Number.parseInt(style.zIndex || '0', 10);
                                if (Number.isNaN(zIndex) || zIndex < 50) continue;
                                const text = (el.innerText || '').toLowerCase();
                                const attrs = `${el.id || ''} ${el.className || ''}`.toLowerCase();
                                const haystack = `${text} ${attrs}`;
                                if (keywords.some((kw) => haystack.includes(kw))) {
                                    tryRemove(el);
                                }
                            }
                        }

                        document.body.style.overflow = 'auto';
                        document.body.style.position = 'static';
                        document.documentElement.style.overflow = 'auto';
                        document.documentElement.style.position = 'static';
                        return removed.size;
                    }
                """)
                if removed:
                    logger.info("Removed %d cookie/overlay DOM elements (frame=%s)", removed, frame.url[:120])
            except Exception as e:
                logger.debug("DOM removal failed for frame %s: %s", frame.url[:120], e)

    async def _remove_cookie_text_elements(self, page: Page) -> None:
        """Scan remaining fixed/sticky elements for cookie-related text and remove them."""
        for frame in self._iter_frames(page):
            try:
                removed = await frame.evaluate("""
                    () => {
                        const keywords = [
                            'cookie', 'cookies', 'consent', 'gdpr', 'privacy policy',
                            'cookie policy', 'cookiebeleid', 'privacybeleid',
                            'we use cookies', 'wij gebruiken cookies',
                            'this website uses cookies', 'deze website gebruikt cookies',
                            'cookie-instellingen', 'cookie settings',
                            'accept cookies', 'cookies accepteren',
                        ];
                        const roots = [document];
                        for (let i = 0; i < roots.length; i++) {
                            const root = roots[i];
                            const hostElements = root.querySelectorAll('*');
                            for (const host of hostElements) {
                                if (host.shadowRoot) roots.push(host.shadowRoot);
                            }
                        }
                        let count = 0;
                        for (const root of roots) {
                            const all = root.querySelectorAll('*');
                            for (const el of all) {
                                const style = getComputedStyle(el);
                                if (style.position !== 'fixed' && style.position !== 'sticky') continue;
                                if (style.display === 'none' || style.visibility === 'hidden') continue;
                                const text = (el.innerText || '').toLowerCase();
                                if (text.length < 5 || text.length > 5000) continue;
                                if (keywords.some(kw => text.includes(kw))) {
                                    el.remove();
                                    count++;
                                }
                            }
                        }
                        return count;
                    }
                """)
                if removed:
                    logger.info("Removed %d cookie-related text elements (frame=%s)", removed, frame.url[:120])
            except Exception as e:
                logger.debug("Cookie text element removal failed for frame %s: %s", frame.url[:120], e)

    def _iter_frames(self, page: Page) -> list[Frame]:
        """Return all current frames, including main frame."""
        return list(page.frames)

    async def _inject_cookie_hide_css(self, frame: Frame) -> None:
        """Inject CSS that hides common consent/cookie containers."""
        try:
            await frame.add_style_tag(content=_CONSENT_HIDE_CSS)
            logger.debug("Injected cookie-hide CSS (frame=%s)", frame.url[:120])
        except Exception as e:
            logger.debug("Cookie-hide CSS injection failed for frame %s: %s", frame.url[:120], e)

    async def _looks_like_cookie_action(self, locator: Locator) -> bool:
        """Check whether a candidate button/link appears to be cookie-related."""
        try:
            return await locator.evaluate(
                """(el, keywords) => {
                    // Do not click regular navigational links for consent handling.
                    if (el.tagName === 'A') {
                        const href = (el.getAttribute('href') || '').trim().toLowerCase();
                        if (href && href !== '#' && !href.startsWith('javascript:')) {
                            return false;
                        }
                    }
                    const own = `${el.innerText || ''} ${el.getAttribute('aria-label') || ''} ${el.id || ''} ${el.className || ''}`.toLowerCase();
                    if (keywords.some((kw) => own.includes(kw))) return true;
                    let node = el;
                    for (let i = 0; i < 5 && node; i++) {
                        const attrs = `${node.id || ''} ${node.className || ''} ${node.getAttribute?.('role') || ''}`.toLowerCase();
                        if (keywords.some((kw) => attrs.includes(kw))) return true;
                        const text = (node.innerText || '').toLowerCase();
                        if (text.length && text.length < 2500 && keywords.some((kw) => text.includes(kw))) {
                            return true;
                        }
                        node = node.parentElement;
                    }
                    return false;
                }""",
                list(_COOKIE_KEYWORDS),
            )
        except Exception:
            return False

    async def _recover_if_unintended_policy_navigation(self, page: Page, requested_url: str) -> None:
        """Recover when consent handling accidentally lands on a policy/legal page."""
        if not self._is_unintended_policy_navigation(requested_url=requested_url, current_url=page.url):
            return

        target_url = self._build_recovery_url(requested_url)
        logger.warning(
            "Detected unintended policy-page navigation (%s) while capturing %s; retrying at %s",
            page.url,
            requested_url,
            target_url,
        )

        await self._navigate_with_fallback(page, target_url)
        await page.wait_for_timeout(400)

        for frame in self._iter_frames(page):
            await self._inject_cookie_hide_css(frame)

        await self._remove_cookie_dom_elements(page)
        await self._remove_cookie_text_elements(page)

    def _is_unintended_policy_navigation(self, requested_url: str, current_url: str) -> bool:
        """True when a root URL request unexpectedly ended on cookie/privacy policy path."""
        requested = urlparse(requested_url)
        current = urlparse(current_url)

        if not requested.netloc or not current.netloc:
            return False
        if requested.netloc != current.netloc:
            return False

        # Respect explicit policy pages when user requested them directly.
        if self._is_policy_path(requested.path):
            return False

        return self._is_policy_path(current.path)

    def _is_policy_path(self, path: str) -> bool:
        """Return True if URL path looks like a cookie/privacy policy page."""
        value = (path or "").strip("/").lower()
        if not value:
            return False
        if any(term in value for term in _POLICY_PATH_TERMS):
            return True
        if "cookie" in value and "policy" in value:
            return True
        if "privacy" in value and "policy" in value:
            return True
        return False

    def _build_root_url(self, url: str) -> str:
        """Build scheme + host root URL from an input URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _build_recovery_url(self, requested_url: str) -> str:
        """Build URL to revisit after unintended policy navigation."""
        requested = urlparse(requested_url)
        if self._is_policy_path(requested.path):
            return self._build_root_url(requested_url)
        return requested_url

    # ── Lazy-load scrolling ──────────────────────────────────────────

    async def _scroll_for_lazy_load(self, page: Page, scroll_pause_ms: int = 300) -> None:
        """Scroll the page to trigger lazy-loaded content."""
        logger.debug("Scrolling page to trigger lazy-loaded content...")

        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")

        current_position = 0
        while current_position < total_height:
            await page.evaluate(f"window.scrollTo(0, {current_position})")
            await page.wait_for_timeout(scroll_pause_ms)
            current_position += viewport_height
            total_height = await page.evaluate("document.body.scrollHeight")

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(scroll_pause_ms)

        logger.debug("Lazy-load scroll complete. Final page height: %dpx", total_height)

    # ── Popup dismissal ──────────────────────────────────────────────

    async def _dismiss_popups(self, page: Page) -> None:
        """Detect and close modal dialogs and overlay popups."""
        logger.debug("Checking for modal popups...")

        close_selectors = [
            '[aria-label="Close"]', '[aria-label="close"]',
            '[aria-label="Sluiten"]', '[aria-label="Dismiss"]',
            'button[class*="close"]', 'button[class*="dismiss"]',
            '[data-dismiss="modal"]',
            '.modal-close', '.popup-close', '.overlay-close', '.dialog-close',
            '.close-button', '.btn-close',
            '[class*="newsletter"] [class*="close"]',
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
        ]

        modal_selectors = [
            '[role="dialog"]', '[role="alertdialog"]',
            '.modal[aria-modal="true"]',
            '[class*="modal"][class*="show"]',
            '[class*="popup"][class*="visible"]',
            '[class*="overlay"][class*="active"]',
        ]

        # Check if any modals are visible
        modal_visible = False
        for selector in modal_selectors:
            try:
                modal = page.locator(selector).first
                if await modal.is_visible(timeout=200):
                    modal_visible = True
                    break
            except Exception:
                continue

        if not modal_visible:
            logger.debug("No modal popups detected")
            return

        # Try to click close buttons
        clicked = False
        for selector in close_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=200):
                    await button.click(timeout=1000)
                    logger.info("Closed popup via: %s", selector)
                    clicked = True
                    await page.wait_for_timeout(300)
                    break
            except Exception:
                continue

        # Fallback: ESC key
        if not clicked:
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
                logger.debug("Sent ESC key to dismiss modals")
            except Exception as e:
                logger.debug("ESC key failed: %s", e)

        # Final fallback: hide modals via CSS
        try:
            await page.add_style_tag(content="""
                [role="dialog"], [role="alertdialog"],
                .modal, [class*="modal"][class*="show"],
                [class*="popup"][class*="visible"],
                [class*="overlay"][class*="active"],
                [class*="newsletter-popup"], [class*="exit-popup"] {
                    display: none !important;
                    visibility: hidden !important;
                }
                body.modal-open { overflow: auto !important; }
            """)
        except Exception as e:
            logger.debug("Modal CSS injection failed: %s", e)

    # ── Accordion expansion ──────────────────────────────────────────

    async def _expand_accordions(self, page: Page) -> None:
        """Expand collapsed accordion sections to reveal hidden content."""
        logger.debug("Expanding accordion sections...")

        try:
            expanded = await page.evaluate("""
                async () => {
                    let count = 0;

                    // HTML5 details elements
                    const details = document.querySelectorAll('details:not([open])');
                    for (const el of details) {
                        el.setAttribute('open', '');
                        count++;
                    }

                    // ARIA accordions
                    const ariaButtons = document.querySelectorAll(
                        '[aria-expanded="false"]:not([disabled])'
                    );
                    for (const btn of ariaButtons) {
                        try {
                            btn.click();
                            count++;
                            await new Promise(r => setTimeout(r, 100));
                        } catch (e) {}
                    }

                    // Common accordion patterns
                    const patterns = [
                        '.accordion-header:not(.active)',
                        '.accordion-toggle:not(.open)',
                        '.collapsible-header:not(.active)',
                        '[data-toggle="collapse"]:not(.collapsed)',
                        '.expand-btn:not(.expanded)',
                    ];
                    for (const selector of patterns) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            try {
                                el.click();
                                count++;
                                await new Promise(r => setTimeout(r, 100));
                            } catch (e) {}
                        }
                    }
                    return count;
                }
            """)

            if expanded > 0:
                logger.info("Expanded %d accordion sections", expanded)
                await page.wait_for_timeout(500)
            else:
                logger.debug("No collapsed accordions found")

        except Exception as e:
            logger.warning("Accordion expansion failed: %s", e)

    # ── Image readiness ──────────────────────────────────────────────

    async def _wait_for_images(self, page: Page, timeout_ms: int = 10000) -> None:
        """Wait until all images are fully loaded."""
        logger.debug("Waiting for images to load...")

        try:
            await page.evaluate("""
                async (timeoutMs) => {
                    const images = Array.from(document.querySelectorAll('img'));
                    const startTime = Date.now();

                    for (const img of images) {
                        if (img.complete && img.naturalWidth > 0) continue;
                        const src = img.src || img.dataset.src;
                        if (!src || src.startsWith('data:image/svg') || src.includes('placeholder')) continue;

                        await new Promise((resolve) => {
                            if (Date.now() - startTime > timeoutMs) { resolve(); return; }
                            if (img.complete && img.naturalWidth > 0) { resolve(); return; }

                            const onDone = () => {
                                img.removeEventListener('load', onDone);
                                img.removeEventListener('error', onDone);
                                resolve();
                            };
                            img.addEventListener('load', onDone);
                            img.addEventListener('error', onDone);
                            setTimeout(resolve, Math.max(0, timeoutMs - (Date.now() - startTime)));
                        });
                    }
                }
            """, timeout_ms)
            logger.debug("All visible images loaded")
        except Exception as e:
            logger.debug("Image wait completed with: %s", e)
