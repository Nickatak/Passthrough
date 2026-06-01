from urllib.parse import urlparse

from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, Response

from camoufox import AsyncNewBrowser

from passthrough.drivers.base import Driver, PageContent


class CamoufoxDriver(Driver):
    """Driver backed by Camoufox (stealth Firefox).

    Holds one long-lived browser -> context -> page. The page is reused
    across requests so cookies, history, and referer chains accumulate
    like a real person's always-on browser. Fingerprinting and stealth
    are handled by Camoufox at the browser level - we don't configure
    per-page stealth here.
    """

    def __init__(self, headless: bool = True):
        """Configure the driver. Does not launch anything - call start() first."""
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._response: Response | None = None

    async def start(self) -> None:
        """Launch Playwright + Camoufox and create the persistent context and page."""
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
        # One context, one reused tab - the persistent session.
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        self._response = None

    async def goto(self, url: str) -> None:
        """Navigate the persistent page and stash the Response for later capture."""
        assert self._page is not None, "Driver not started"
        response = await self._page.goto(url, wait_until="domcontentloaded")
        if response is not None:
            self._response = response

    def page(self) -> Page:
        """Return the persistent page for adapter inspection and solving."""
        assert self._page is not None, "Driver not started"
        return self._page

    async def capture(self) -> PageContent:
        """Extract status, headers, cookies, and body from the persistent page.

        Cookies are filtered to the navigated host: the shared jar holds every
        visited site's cookies, but a caller only gets the host it asked for.
        """
        assert self._page is not None, "Driver not started"
        response = self._response

        status = response.status if response else 0
        headers = dict(await response.all_headers()) if response else {}

        host = urlparse(self._page.url).hostname or ""
        cookies_raw = await self._context.cookies()
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
            if self._cookie_matches_host(c["domain"], host)
        ]

        body = await self._page.content()

        return PageContent(
            status=status,
            headers=headers,
            cookies=cookies,
            body=body,
        )

    @staticmethod
    def _cookie_matches_host(cookie_domain: str, host: str) -> bool:
        """True if a cookie's domain covers host (exact match or parent domain).

        Cookie domains may carry a leading dot (e.g. '.ebay.com'), which the
        spec treats as "this domain and all subdomains". So '.ebay.com' and
        'ebay.com' both cover 'www.ebay.com'.
        """
        d = cookie_domain.lstrip(".")
        return host == d or host.endswith("." + d)

    async def restart(self) -> None:
        """Nuke the whole browser and relaunch fresh - new fingerprint, empty jar."""
        await self.stop()
        await self.start()

    async def stop(self) -> None:
        """Shut down the browser and Playwright, clearing all session handles."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._context = None
        self._page = None
        self._response = None
