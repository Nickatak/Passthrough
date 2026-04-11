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

    A driver manages browser lifecycle and page interaction.
    The pipeline calls these methods - it never touches browser
    APIs directly.
    """

    @abstractmethod
    async def start(self) -> None:
        """Launch the browser. Called once at app startup."""
        ...

    @abstractmethod
    async def new_page(self) -> Page:
        """Create a new browser page with stealth config applied."""
        ...

    @abstractmethod
    async def goto(self, page: Page, url: str) -> None:
        """Navigate to url. Waits for domcontentloaded."""
        ...

    @abstractmethod
    async def capture(self, page: Page) -> PageContent:
        """Extract status, headers, cookies, and body from the current page."""
        ...

    @abstractmethod
    async def close_page(self, page: Page) -> None:
        """Close a page and release its resources."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Shut down the browser. Called once at app shutdown."""
        ...
