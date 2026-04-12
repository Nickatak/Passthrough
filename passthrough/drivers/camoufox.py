from playwright.async_api import async_playwright, Playwright, Browser, Page, Response

from camoufox import AsyncNewBrowser

from passthrough.drivers.base import Driver, PageContent


class CamoufoxDriver(Driver):
    """Driver backed by Camoufox (stealth Firefox).

    Uses AsyncNewBrowser for explicit lifecycle control. Fingerprinting
    and stealth are handled by Camoufox at the browser level - we don't
    configure per-page stealth here.
    """

    def __init__(self, headless: bool = True):
        """Configure the driver. Does not launch anything - call start() first."""
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._responses: dict[Page, Response] = {}

    async def start(self) -> None:
        """Launch Playwright and the Camoufox browser."""
        self._playwright = await async_playwright().start()
        self._browser = await AsyncNewBrowser(
            self._playwright,
            headless=self._headless,
            # Generate realistic mouse curves and timing on click actions
            # so automation doesn't look like instant teleport-and-click.
            humanize=True,
            # Disable Cross-Origin Opener Policy so Playwright can reach
            # into cross-origin iframes (e.g. Cloudflare Turnstile widget).
            # Safe here because this browser has no user session to protect.
            disable_coop=True,
            # Required acknowledgment for disable_coop - Camoufox's way of
            # confirming you understand the security implications.
            i_know_what_im_doing=True,
        )

    async def new_page(self) -> Page:
        """Create a fresh page in its own browser context for isolation."""
        assert self._browser is not None, "Driver not started"
        context = await self._browser.new_context()
        page = await context.new_page()
        return page

    async def goto(self, page: Page, url: str) -> None:
        """Navigate and stash the Response for later capture."""
        response = await page.goto(url, wait_until="domcontentloaded")
        if response is not None:
            self._responses[page] = response

    async def capture(self, page: Page) -> PageContent:
        """Extract status, headers, cookies, and body from the current page state."""
        response = self._responses.get(page)

        status = response.status if response else 0
        headers = dict(await response.all_headers()) if response else {}

        cookies_raw = await page.context.cookies()
        cookies = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "expires": c.get("expires", None),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
            }
            for c in cookies_raw
        ]

        body = await page.content()

        return PageContent(
            status=status,
            headers=headers,
            cookies=cookies,
            body=body,
        )

    async def close_page(self, page: Page) -> None:
        """Close the page, its context, and clean up the stashed response."""
        context = page.context
        self._responses.pop(page, None)
        await page.close()
        await context.close()

    async def stop(self) -> None:
        """Shut down the browser and Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
