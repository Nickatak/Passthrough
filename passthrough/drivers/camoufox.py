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
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._responses: dict[Page, Response] = {}

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await AsyncNewBrowser(
            self._playwright,
            headless=self._headless,
            humanize=True,
            disable_coop=True,
            i_know_what_im_doing=True,
        )

    async def new_page(self) -> Page:
        assert self._browser is not None, "Driver not started"
        context = await self._browser.new_context()
        page = await context.new_page()
        return page

    async def goto(self, page: Page, url: str) -> None:
        response = await page.goto(url, wait_until="domcontentloaded")
        if response is not None:
            self._responses[page] = response

    async def capture(self, page: Page) -> PageContent:
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
        context = page.context
        self._responses.pop(page, None)
        await page.close()
        await context.close()

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
