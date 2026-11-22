"""Lidl Netherlands, from the public offers page on lidl.nl.

The page https://www.lidl.nl/c/aanbiedingen/a10008785 lists the whole offer
week (Monday offers and the ones starting Thursday). Every product tile carries
its data as JSON in a `data-grid-data` HTML attribute: title, price, Lidl Plus
price, the in-store start and end dates and a category path. robots.txt allows
this page. One request per run.

If Lidl changes the page so that no tiles are found, `offers()` raises instead
of returning an empty list, so the failure gets reported.
"""
import html
import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field

from grocery_assistant import __version__
from grocery_assistant.models import Offer

log = logging.getLogger(__name__)

BASE = "https://www.lidl.nl"
OFFERS_PAGE = f"{BASE}/c/aanbiedingen/a10008785"
USER_AGENT = f"grocery-assistant/{__version__} (+https://github.com/echbremmer/grocery-assistant)"
TZ = ZoneInfo("Europe/Amsterdam")
GRID_DATA = re.compile(r'data-grid-data="([^"]*)"')


class PageChanged(RuntimeError):
    """The offers page no longer looks the way this module expects."""


class _Packaging(BaseModel):
    text: str | None = None


class _Price(BaseModel):
    model_config = ConfigDict(extra="ignore")
    price: float | None = None
    old_price: float | None = Field(default=None, alias="oldPrice")
    packaging: _Packaging | None = None


class _LidlPlus(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    price: _Price | None = None
    text: str | None = Field(default=None, alias="lidlPlusText")
    highlight: str | None = Field(default=None, alias="highlightText")


class _Keyfacts(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # e.g. "Werelden van nood/Eten en dichtbij voedsel/Vlees & gevogelte/Rundvlees"
    wonCategoryPrimary: str | None = None


class LidlItem(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    product_id: int = Field(alias="productId")
    full_title: str = Field(alias="fullTitle")
    canonical_path: str = Field(alias="canonicalPath")
    price: _Price | None = None
    lidl_plus: list[_LidlPlus] | None = Field(default=None, alias="lidlPlus")
    store_start: int | None = Field(default=None, alias="storeStartDate")
    store_end: int | None = Field(default=None, alias="storeEndDate")
    keyfacts: _Keyfacts | None = None

    @property
    def category_path(self) -> list[str]:
        path = (self.keyfacts.wonCategoryPrimary if self.keyfacts else None) or ""
        return [p.strip() for p in path.split("/") if p.strip()]

    def to_offer(self) -> Offer:
        path = self.category_path
        price = self.price or _Price()
        lp = next((x for x in self.lidl_plus or [] if x.price and x.price.price is not None), None)
        return Offer(
            store="lidl",
            product_id=str(self.product_id),
            # Products without a brand come as "- Kipfilet"
            title=re.sub(r"^[\s-]+", "", self.full_title).strip(),
            url=BASE + self.canonical_path,
            # path[0] is a root ("Werelden van nood"), [1] the department, [2] the category
            category=path[2] if len(path) > 2 else None,
            sub_category=path[3] if len(path) > 3 else None,
            start=_day(self.store_start),
            end=_day(self.store_end),
            size=price.packaging.text if price.packaging else None,
            price=price.price,
            price_before=price.old_price,
            member_price=lp.price.price if lp else None,
            member_label=(lp.text or "met Lidl Plus") if lp else None,
            # The highlight is usually the discount ("-26%"), but sometimes the pack size
            member_discount=lp.highlight if lp and _is_discount(lp.highlight) else None,
        )


def _is_discount(text: str | None) -> bool:
    return bool(text) and ("%" in text or text.strip().startswith("-"))


def _day(ts: int | None) -> date | None:
    return datetime.fromtimestamp(ts, TZ).date() if ts else None


def parse_offers_page(page: str) -> list[Offer]:
    raw = GRID_DATA.findall(page)
    if not raw:
        raise PageChanged("no product tiles (data-grid-data) found on the Lidl offers page")
    offers, seen = [], set()
    for attr in raw:
        item = LidlItem.model_validate_json(html.unescape(attr))
        if item.product_id not in seen:  # a product can appear in two sections
            seen.add(item.product_id)
            offers.append(item.to_offer())
    log.debug("lidl: %s offers on the page", len(offers))
    return offers


class LidlClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "nl-NL"},
            timeout=60,
            follow_redirects=True,
            transport=transport or httpx.HTTPTransport(retries=3),
        )

    def __enter__(self) -> "LidlClient":
        return self

    def __exit__(self, *exc) -> None:
        self._client.close()

    def offers(self) -> list[Offer]:
        r = self._client.get(OFFERS_PAGE)
        r.raise_for_status()
        return parse_offers_page(r.text)
