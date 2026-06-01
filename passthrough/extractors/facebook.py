import json
import re

from passthrough.drivers.base import PageContent
from passthrough.extractors.base import Extractor

# Facebook ships page data inside <script type="application/json"> blobs
# (the __bbox / RelayPrefetchedStreamCache payload), not as rendered HTML.
_JSON_SCRIPT = re.compile(
    r'<script[^>]+type="application/json"[^>]*>(.*?)</script>', re.S
)


class FacebookMarketplaceExtractor(Extractor):
    """Pull Marketplace listings out of Facebook's embedded Relay JSON.

    Search and listing results are not rendered into HTML - they sit in the
    JSON blobs Facebook streams into <script> tags. We parse each blob and
    walk it for listing objects: any dict carrying a 'marketplace_listing_title'
    key. Walking by key rather than by a fixed path keeps this resilient to
    Facebook reshuffling the surrounding nesting, which they do often.
    """

    @property
    def name(self) -> str:
        return "fb_marketplace"

    def extract(self, content: PageContent) -> dict:
        """Return {'count', 'listings': [...]} flattened from the page JSON."""
        listings = []
        seen: set[str] = set()
        for blob in _JSON_SCRIPT.findall(content.body):
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue  # not every json-typed script is valid or relevant
            for node in self._find_listings(data):
                record = self._to_record(node)
                if record and record["id"] not in seen:
                    seen.add(record["id"])
                    listings.append(record)
        return {"count": len(listings), "listings": listings}

    def _find_listings(self, obj):
        """Recursively yield every dict that looks like a Marketplace listing."""
        if isinstance(obj, dict):
            if "marketplace_listing_title" in obj:
                yield obj
            for value in obj.values():
                yield from self._find_listings(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from self._find_listings(value)

    def _to_record(self, node: dict) -> dict | None:
        """Flatten one Facebook listing object into a clean record.

        Defensive .get() chains throughout: a missing sub-field yields None
        for that key rather than dropping the whole listing.
        """
        listing_id = node.get("id")
        if not listing_id:
            return None

        price = node.get("listing_price") or {}
        photo = (node.get("primary_listing_photo") or {}).get("image") or {}
        geo = (node.get("location") or {}).get("reverse_geocode") or {}

        location = (geo.get("city_page") or {}).get("display_name")
        if not location and geo.get("city"):
            location = f"{geo['city']}, {geo.get('state', '')}".rstrip(", ")

        return {
            "id": listing_id,
            "title": node.get("marketplace_listing_title"),
            "price": price.get("formatted_amount"),
            "amount": price.get("amount"),
            "location": location,
            "url": f"https://www.facebook.com/marketplace/item/{listing_id}",
            "photo": photo.get("uri"),
            "is_sold": node.get("is_sold"),
        }
