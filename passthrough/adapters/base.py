from abc import ABC, abstractmethod
from enum import Enum
from playwright.async_api import Page


class DetectResult(Enum):
    CLEAR = "clear"           # Not a challenge page - real content
    CHALLENGED = "challenged"  # Challenge detected, solvable
    BLOCKED = "blocked"        # Provider blocked us, no solve path


class ChallengeAdapter(ABC):
    """Interface for challenge provider adapters.

    Each adapter knows how to detect and solve challenges from
    a specific provider (Cloudflare, DataDome, etc). The pipeline
    iterates through registered adapters - first one to claim
    the page owns the solve cycle.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'cloudflare'. Used for logging and error messages."""
        ...

    @abstractmethod
    async def detect(self, page: Page) -> DetectResult:
        """Check whether this provider is challenging the page.

        Called after initial navigation. Should check cheap signals
        first (status code, headers) before expensive ones (DOM inspection).
        """
        ...

    @abstractmethod
    async def solve(self, page: Page) -> None:
        """Attempt to solve the challenge.

        Only called when detect() returned CHALLENGED. After solve
        completes, the browser should be on the real page (the
        provider redirects automatically after granting clearance).

        Raises on failure - the pipeline catches and reports.
        """
        ...
