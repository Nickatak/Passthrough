from abc import ABC, abstractmethod
from dataclasses import dataclass
from playwright.async_api import Page


@dataclass
class PageContent:
    """Everything the pipeline needs from a loaded page."""

    status: int
    headers: dict[str, str]
    cookies: list[dict]
    body: str


class Driver(ABC):
    """Interface for browser drivers.

    A driver manages a single, long-lived browser session: one browser,
    one context, one reused tab that accumulates cookies and history
    across requests like a real person's always-on browser. The pipeline
    calls these methods - it never touches browser APIs directly.
    """

    @abstractmethod
    async def start(self) -> None:
        """Launch the browser and create the persistent context and page.

        Called once at app startup, and again by restart() after a nuke.
        """
        ...

    @abstractmethod
    async def goto(self, url: str) -> None:
        """Navigate the persistent page to url. Waits for domcontentloaded."""
        ...

    @abstractmethod
    def page(self) -> Page:
        """Return the persistent page so adapters can inspect and act on it."""
        ...

    @abstractmethod
    def is_alive(self) -> bool:
        """True if the browser session is live and usable.

        False after the underlying browser subprocess has crashed (handles
        linger but the connection is dead). The pipeline checks this before a
        request and rebuilds the driver if it returns False.
        """
        ...

    @abstractmethod
    async def capture(self) -> PageContent:
        """Extract status, headers, cookies, and body from the persistent page.

        Cookies are filtered to the navigated host - the shared jar holds
        every visited site's cookies, but a caller only gets the one it asked for.
        """
        ...

    @abstractmethod
    async def restart(self) -> None:
        """Nuke the whole browser and relaunch a fresh one.

        Rotates the browser identity: new fingerprint, empty cookie jar,
        brand-new tab. The panic button for when the current identity is
        flagged or the tab is wedged. Does not change the egress IP.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Shut down the browser. Called once at app shutdown."""
        ...
