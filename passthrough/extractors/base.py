from abc import ABC, abstractmethod

from passthrough.drivers.base import PageContent


class Extractor(ABC):
    """Post-processing layer: turn a captured page into structured data.

    Runs after the driver captures the page, before the response is returned.
    Where adapters handle getting *through* a wall, extractors handle getting
    the *data* out of what comes back. Selected explicitly by the caller via
    the /request/{extractor} route - the route token is the extractor's name.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Route token, e.g. 'fb_marketplace'. Matched against /request/{name}."""
        ...

    @abstractmethod
    def extract(self, content: PageContent) -> dict:
        """Parse structured data out of the captured page.

        Operates on the raw body string - no live browser access. Returns a
        JSON-serializable dict. May raise on parse failure; the pipeline
        catches it and degrades to returning the raw body with an error note.
        """
        ...
