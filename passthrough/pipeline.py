import asyncio
from urllib.parse import urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from passthrough.adapters.base import ChallengeAdapter, DetectResult
from passthrough.drivers.base import Driver, PageContent
from passthrough.errors import (
    ChallengeBlocked,
    CaptureFailed,
    InvalidRequest,
    NavigationFailed,
    SolveFailed,
)


class Pipeline:
    """Orchestrates the request flow: receive -> navigate -> detect -> solve -> capture -> return.

    Works entirely through the Driver and ChallengeAdapter interfaces.
    Does not know which browser or which providers are in use.

    The driver holds one reused tab, so every request operates on shared
    browser state. A lock serializes the whole flow (and restart) - one
    request at a time, which is also how the tool is used in practice.
    """

    def __init__(self, driver: Driver, adapters: list[ChallengeAdapter]):
        """Wire up the driver and adapters. Order of adapters = detection priority."""
        self.driver = driver
        self.adapters = adapters
        self._lock = asyncio.Lock()

    async def process(self, url: str, method: str = "GET") -> PageContent:
        # Step 1: Receive - validate before touching a browser
        self._validate(url, method)

        # Serialize the whole flow: navigate -> detect -> solve -> capture all
        # operate on the one shared tab and must not interleave with another
        # request or a restart.
        async with self._lock:
            page = self.driver.page()

            # Step 2: Navigate
            await self._navigate(url)

            # Step 3: Detect - check registered adapters
            adapter = await self._detect(page)

            # Step 4: Solve - if an adapter claimed the page
            if adapter is not None:
                await self._solve(adapter, page, url)

            # Step 5: Capture
            return await self._capture()

    async def restart(self) -> None:
        """Nuke and relaunch the browser. Holds the lock so it can't run mid-request."""
        async with self._lock:
            await self.driver.restart()

    def _validate(self, url: str, method: str) -> None:
        """Reject bad input before touching a browser."""
        if method.upper() != "GET":
            raise InvalidRequest(f"Unsupported method: {method}. Only GET is supported.")

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise InvalidRequest(f"Invalid URL scheme: {parsed.scheme!r}. Must be http or https.")
        if not parsed.netloc:
            raise InvalidRequest(f"Invalid URL: missing host.")

    async def _navigate(self, url: str) -> None:
        """Delegate navigation to the driver, wrapping failures as NavigationFailed."""
        try:
            await self.driver.goto(url)
        except PlaywrightTimeout:
            raise NavigationFailed(f"Timed out navigating to {url}")
        except Exception as exc:
            raise NavigationFailed(f"Failed to navigate to {url}: {exc}")

    async def _detect(self, page: Page) -> ChallengeAdapter | None:
        """Run adapters in registration order. First to claim the page wins."""
        for adapter in self.adapters:
            result = await adapter.detect(page)

            if result == DetectResult.BLOCKED:
                raise ChallengeBlocked(f"{adapter.name} blocked the request with no solve path.")

            if result == DetectResult.CHALLENGED:
                return adapter

        # No adapter claimed it - page is clear
        return None

    async def _solve(self, adapter: ChallengeAdapter, page: Page, url: str) -> None:
        """Run the adapter's solve, then re-navigate to capture a clean response."""
        try:
            await adapter.solve(page)
        except Exception as exc:
            raise SolveFailed(f"{adapter.name} solve failed: {exc}")

        # Re-navigate to get a clean Response for capture.
        # After solve, the browser has cf_clearance cookies, so
        # this returns the real page with correct status/headers.
        await self._navigate(url)

    async def _capture(self) -> PageContent:
        """Pull page content from the driver, wrapping failures as CaptureFailed."""
        try:
            return await self.driver.capture()
        except Exception as exc:
            raise CaptureFailed(f"Failed to capture page content: {exc}")
