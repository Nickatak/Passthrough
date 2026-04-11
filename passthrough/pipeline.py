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
    """Orchestrates the request flow: receive -> prepare -> navigate -> detect -> solve -> capture -> return.

    Works entirely through the Driver and ChallengeAdapter interfaces.
    Does not know which browser or which providers are in use.
    """

    def __init__(self, driver: Driver, adapters: list[ChallengeAdapter]):
        self.driver = driver
        self.adapters = adapters

    async def process(self, url: str, method: str = "GET") -> PageContent:
        # Step 1: Receive - validate before touching a browser
        self._validate(url, method)

        page: Page | None = None
        try:
            # Step 2: Prepare - stealth config is the driver's responsibility
            page = await self.driver.new_page()

            # Step 3: Navigate
            await self._navigate(page, url)

            # Step 4: Detect - check registered adapters
            adapter = await self._detect(page)

            # Step 5: Solve - if an adapter claimed the page
            if adapter is not None:
                await self._solve(adapter, page)

            # Step 6: Capture
            return await self._capture(page)

        finally:
            # Always release the page, even on failure
            if page is not None:
                await self.driver.close_page(page)

    def _validate(self, url: str, method: str) -> None:
        if method.upper() != "GET":
            raise InvalidRequest(f"Unsupported method: {method}. Only GET is supported.")

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise InvalidRequest(f"Invalid URL scheme: {parsed.scheme!r}. Must be http or https.")
        if not parsed.netloc:
            raise InvalidRequest(f"Invalid URL: missing host.")

    async def _navigate(self, page: Page, url: str) -> None:
        try:
            await self.driver.goto(page, url)
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

    async def _solve(self, adapter: ChallengeAdapter, page: Page) -> None:
        try:
            await adapter.solve(page)
        except Exception as exc:
            raise SolveFailed(f"{adapter.name} solve failed: {exc}")

    async def _capture(self, page: Page) -> PageContent:
        try:
            return await self.driver.capture(page)
        except Exception as exc:
            raise CaptureFailed(f"Failed to capture page content: {exc}")
