from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from passthrough.adapters.base import ChallengeAdapter, DetectResult


_CLEARANCE_TIMEOUT = 30_000      # Total budget for orchestrator to grant clearance
_IFRAME_INJECT_TIMEOUT = 5_000   # Bound for the orchestrator to inject a Turnstile widget

# Substrings that uniquely identify the Cloudflare challenge orchestrator
# in raw HTML. These survive customer branding (e.g. Indeed renames the
# title to "Security Check - Indeed.com") because they live in the script
# bundle, not the rendered chrome.
_CHALLENGE_HTML_MARKERS = (
    "_cf_chl_opt",
    "/cdn-cgi/challenge-platform/",
)

_BLOCKED_BODY_MARKERS = (
    "Access denied",
    "Sorry, you have been blocked",
)

# Predicate used to wait for the orchestrator to finish. The _cf_chl_opt
# global is defined while the challenge page is live and goes away when
# Cloudflare swaps in the real page. Robust against customer-branded
# titles, unlike the older `document.title !== 'Just a moment...'` check.
_CLEARANCE_PREDICATE = "() => typeof window._cf_chl_opt === 'undefined'"

_TURNSTILE_IFRAME_SELECTOR = "iframe[src*='challenges.cloudflare.com/turnstile']"


class CloudflareAdapter(ChallengeAdapter):
    """Detects and solves Cloudflare challenges.

    Handles three variants with one solve strategy:
      - JS challenge ("Checking your browser..." auto-clear)
      - Static Turnstile (checkbox iframe in initial HTML)
      - Orchestrated interactive captcha (widget injected at runtime,
        often with customer-branded chrome — e.g. Indeed /jobs)

    Block pages are detected but unsolvable.
    """

    @property
    def name(self) -> str:
        return "cloudflare"

    async def detect(self, page: Page) -> DetectResult:
        """Classify the page as clear, challenged, or blocked.

        Checks the rendered body text for block-page language first,
        then the raw HTML for the orchestrator's signature. Title
        is no longer load-bearing — customers can customize it.
        """
        body_text = await page.locator("body").inner_text()
        if any(marker in body_text for marker in _BLOCKED_BODY_MARKERS):
            return DetectResult.BLOCKED

        html = await page.content()
        if any(marker in html for marker in _CHALLENGE_HTML_MARKERS):
            return DetectResult.CHALLENGED

        # Legacy fallback: a "Just a moment..." page that somehow lacks
        # the orchestrator markers (older variants, edge cases).
        if await page.title() == "Just a moment...":
            return DetectResult.CHALLENGED

        return DetectResult.CLEAR

    async def solve(self, page: Page) -> None:
        """Wait briefly for an interactive widget, click it if present, then wait for clearance.

        The same flow handles auto-clear JS challenges and
        click-required Turnstile variants — if no iframe is injected
        within the bounded wait, we proceed straight to the clearance
        wait, which auto-clear challenges satisfy on their own.
        """
        try:
            await page.wait_for_selector(
                _TURNSTILE_IFRAME_SELECTOR,
                timeout=_IFRAME_INJECT_TIMEOUT,
                state="visible",
            )
            await self._click_turnstile_checkbox(page)
        except PlaywrightTimeout:
            # No interactive widget appeared — assume auto-clear variant.
            pass

        await page.wait_for_function(
            _CLEARANCE_PREDICATE,
            timeout=_CLEARANCE_TIMEOUT,
        )
        await page.wait_for_load_state("load", timeout=_CLEARANCE_TIMEOUT)

    async def _click_turnstile_checkbox(self, page: Page) -> None:
        """Click into the Turnstile iframe's checkbox.

        Camoufox's humanize generates a realistic mouse curve; disable_coop
        on the driver allows reaching into the cross-origin iframe.
        """
        turnstile_frame = page.frame_locator(_TURNSTILE_IFRAME_SELECTOR)
        checkbox = turnstile_frame.locator(
            "input[type='checkbox'], div[role='checkbox'], .ctp-checkbox-label"
        )
        await checkbox.click(timeout=_CLEARANCE_TIMEOUT)
