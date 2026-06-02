import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from passthrough.adapters.base import ChallengeAdapter, DetectResult
from passthrough.drivers.base import Driver, PageContent
from passthrough.extractors.base import Extractor
from passthrough.errors import (
    ChallengeBlocked,
    CaptureFailed,
    InvalidRequest,
    NavigationFailed,
    SolveFailed,
    UnknownExtractor,
)


@dataclass
class ProcessResult:
    """Outcome of a request: the raw capture plus optional extracted data.

    `extracted` is set when an extractor ran and succeeded; `extract_error`
    is set when one ran and failed (the raw content is still returned so the
    caller can fall back).
    """

    content: PageContent
    extracted: dict | None = None
    extract_error: str | None = None


class Pipeline:
    """Orchestrates the request flow: navigate -> detect -> solve -> capture -> extract -> return.

    Works entirely through the Driver, ChallengeAdapter, and Extractor interfaces.
    Does not know which browser or which providers are in use.

    The driver holds one reused tab, so every request operates on shared
    browser state. A lock serializes the browser-touching part of the flow
    (and restart) - one request at a time, which is also how the tool is used
    in practice. Extraction runs after the lock: it's pure parsing of the
    captured string and needs no browser access.
    """

    def __init__(
        self,
        driver: Driver,
        adapters: list[ChallengeAdapter],
        extractors: list[Extractor] | None = None,
    ):
        """Wire up the driver, adapters, and extractors.

        Order of adapters = detection priority. Extractors are keyed by name
        for /request/{extractor} lookup.
        """
        self.driver = driver
        self.adapters = adapters
        self._extractors = {e.name: e for e in (extractors or [])}
        self._lock = asyncio.Lock()

    async def process(
        self, url: str, method: str = "GET", extractor: str | None = None
    ) -> ProcessResult:
        # Step 1: Receive - validate before touching a browser. Resolve the
        # extractor up front too, so a bogus name fails fast without a fetch.
        self._validate(url, method)
        ext = self._resolve_extractor(extractor)

        # Serialize the browser-touching flow: navigate -> detect -> solve ->
        # capture all operate on the one shared tab and must not interleave
        # with another request or a restart.
        async with self._lock:
            # Step 0: Auto-heal. A prior request can crash the browser
            # subprocess (e.g. an unguarded page-error in the Playwright driver
            # triggered by a hostile page). The handles linger but the
            # connection is dead, so rebuild before touching the tab - otherwise
            # every request 502s until a manual container restart. Call the
            # driver's restart directly, not self.restart(), which re-locks.
            if not self.driver.is_alive():
                await self.driver.restart()

            page = self.driver.page()

            # Step 2: Navigate
            await self._navigate(url)

            # Step 3: Detect - check registered adapters
            adapter = await self._detect(page)

            # Step 4: Solve - if an adapter claimed the page
            if adapter is not None:
                await self._solve(adapter, page, url)

            # Step 5: Capture
            content = await self._capture()

        # Step 6: Extract (outside the lock - pure parsing, no browser access)
        if ext is None:
            return ProcessResult(content=content)
        try:
            return ProcessResult(content=content, extracted=ext.extract(content))
        except Exception as exc:
            # A parse failure doesn't fail the fetch - hand back the raw body
            # so the caller isn't empty-handed, with the error attached.
            return ProcessResult(content=content, extract_error=f"{ext.name} extraction failed: {exc}")

    async def restart(self) -> None:
        """Nuke and relaunch the browser. Holds the lock so it can't run mid-request."""
        async with self._lock:
            await self.driver.restart()

    def _resolve_extractor(self, name: str | None) -> Extractor | None:
        """Look up a requested extractor by name, or None if none was requested."""
        if name is None:
            return None
        ext = self._extractors.get(name)
        if ext is None:
            available = sorted(self._extractors) or ["(none registered)"]
            raise UnknownExtractor(f"No extractor named {name!r}. Available: {available}")
        return ext

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
