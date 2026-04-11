from enum import Enum, auto

from playwright.async_api import Page

from passthrough.adapters.base import ChallengeAdapter, DetectResult


class _ChallengeType(Enum):
    JS_CHALLENGE = auto()
    TURNSTILE = auto()


_JS_CHALLENGE_TIMEOUT = 15_000  # JS challenges typically resolve in 3-8s
_TURNSTILE_TIMEOUT = 30_000     # Turnstile has animation + verification cycle


class CloudflareAdapter(ChallengeAdapter):
    """Detects and solves Cloudflare challenges.

    Supports JS challenges (auto-solving "Checking your browser..." pages)
    and Turnstile (interactive checkbox widget). Block pages are detected
    but unsolvable.
    """

    def __init__(self) -> None:
        # Keyed by Page to avoid concurrency issues if multiple
        # requests share the same adapter instance.
        self._challenge_types: dict[Page, _ChallengeType] = {}

    @property
    def name(self) -> str:
        return "cloudflare"

    async def detect(self, page: Page) -> DetectResult:
        title = await page.title()

        if title != "Just a moment...":
            # Not a challenge page. Could still be a block page -
            # those can have titles like "Attention Required!"
            body_text = await page.locator("body").inner_text()
            if "Access denied" in body_text or "Sorry, you have been blocked" in body_text:
                return DetectResult.BLOCKED
            return DetectResult.CLEAR

        # Title is "Just a moment..." - this is a Cloudflare interstitial.
        # Determine if it's a solvable challenge or a block.

        body_text = await page.locator("body").inner_text()
        if "Access denied" in body_text or "Sorry, you have been blocked" in body_text:
            return DetectResult.BLOCKED

        # Check for Turnstile before JS challenge - Turnstile requires
        # explicit interaction and should take priority if both are present.
        turnstile_iframe = page.locator("iframe[src*='challenges.cloudflare.com/turnstile']")
        turnstile_div = page.locator("div.cf-turnstile, div[data-sitekey]")
        if await turnstile_iframe.count() > 0 or await turnstile_div.count() > 0:
            self._challenge_types[page] = _ChallengeType.TURNSTILE
            return DetectResult.CHALLENGED

        # Title says "Just a moment..." with no Turnstile elements.
        # This is a JS challenge (or an unknown variant - either way,
        # waiting for the title to change is the right move).
        self._challenge_types[page] = _ChallengeType.JS_CHALLENGE
        return DetectResult.CHALLENGED

    async def solve(self, page: Page) -> None:
        challenge_type = self._challenge_types.pop(page, None)
        if challenge_type is None:
            raise RuntimeError("solve() called without prior detect()")

        if challenge_type == _ChallengeType.JS_CHALLENGE:
            await self._solve_js_challenge(page)
        elif challenge_type == _ChallengeType.TURNSTILE:
            await self._solve_turnstile(page)

    async def _solve_js_challenge(self, page: Page) -> None:
        # JS challenges auto-solve - Cloudflare's JS runs environment
        # checks and auto-submits if the browser passes. We just wait
        # for the title to change, signaling the redirect to the real page.
        await page.wait_for_function(
            "document.title !== 'Just a moment...'",
            timeout=_JS_CHALLENGE_TIMEOUT,
        )
        await page.wait_for_load_state("load", timeout=_JS_CHALLENGE_TIMEOUT)

    async def _solve_turnstile(self, page: Page) -> None:
        # Locate the Turnstile iframe and click the checkbox inside it.
        # Camoufox's humanize handles mouse movement; disable_coop
        # allows clicking into the cross-origin iframe.
        turnstile_frame = page.frame_locator(
            "iframe[src*='challenges.cloudflare.com/turnstile']"
        )
        checkbox = turnstile_frame.locator(
            "input[type='checkbox'], div[role='checkbox'], .ctp-checkbox-label"
        )
        await checkbox.click(timeout=_TURNSTILE_TIMEOUT)

        # Wait for the challenge to validate and redirect to the real page.
        await page.wait_for_function(
            "document.title !== 'Just a moment...'",
            timeout=_TURNSTILE_TIMEOUT,
        )
        await page.wait_for_load_state("load", timeout=_TURNSTILE_TIMEOUT)
