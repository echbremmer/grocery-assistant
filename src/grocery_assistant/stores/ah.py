"""Albert Heijn, through the AH app API (api.ah.nl).

This is the API the Appie app uses. It is undocumented and can change without
notice. ah.nl itself refuses automated requests (HTTP 403), so this is the only
practical source.

- Anonymous token: POST /mobile-auth/v1/auth/token/anonymous {"clientId": "appie"}
- Search: GET /mobile-services/product/search/v2 with filters=bonus=Bonus and
  taxonomyId=<category>. One search returns at most 3,000 products, which is
  why we search per top-level category instead of all bonus products at once.
"""
import logging
import time
from collections.abc import Iterator

import httpx

from grocery_assistant.models import Product

log = logging.getLogger(__name__)

API = "https://api.ah.nl"
HEADERS = {
    "User-Agent": "Appie/8.22.3",
    "x-application": "AHWEBSHOP",
    "x-client-name": "appie-android",
    "x-client-version": "8.22.3",
    "Accept": "application/json",
}
PAGE_SIZE = 500
MAX_PAGES = 6  # 6 x 500 = the API's 3,000-result window
PAUSE = 1.0  # seconds between requests, to stay polite


class AHClient:
    def __init__(self, transport: httpx.BaseTransport | None = None, pause: float = PAUSE):
        self._client = httpx.Client(
            base_url=API,
            headers=HEADERS,
            timeout=60,
            transport=transport or httpx.HTTPTransport(retries=3),
        )
        self._pause = pause
        self._token: str | None = None

    def __enter__(self) -> "AHClient":
        return self

    def __exit__(self, *exc) -> None:
        self._client.close()

    def _auth(self) -> dict[str, str]:
        if self._token is None:
            r = self._client.post(
                "/mobile-auth/v1/auth/token/anonymous", json={"clientId": "appie"}
            )
            r.raise_for_status()
            self._token = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def bonus_products(self, taxonomy_id: int) -> Iterator[Product]:
        """All bonus products (any type, any period) the API lists for a category."""
        for page in range(MAX_PAGES):
            r = self._client.get(
                "/mobile-services/product/search/v2",
                params={
                    "filters": "bonus=Bonus",
                    "taxonomyId": taxonomy_id,
                    "size": PAGE_SIZE,
                    "page": page,
                },
                headers=self._auth(),
            )
            r.raise_for_status()
            items = r.json().get("products", [])
            log.debug("category %s page %s: %s products", taxonomy_id, page, len(items))
            for item in items:
                yield Product.model_validate(item)
            if len(items) < PAGE_SIZE:
                return
            time.sleep(self._pause)
        log.warning("category %s hit the %s-result limit; list may be cut off",
                    taxonomy_id, PAGE_SIZE * MAX_PAGES)
