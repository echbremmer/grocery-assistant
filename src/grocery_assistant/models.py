"""Data models.

`Offer` is what the formatter works with, the same for every store. Each store
module validates its own raw API/page data with pydantic and maps it to
`Offer`. Only the fields we use are declared; anything else in the store's data
is ignored, so new fields don't break anything, while a missing or renamed
field we do use fails validation with a clear error.
"""
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class Offer:
    store: str
    product_id: str
    title: str
    url: str
    category: str | None  # the store's category name, matched against the query
    sub_category: str | None  # used for sorting within a section
    start: date | None
    end: date | None
    size: str | None = None
    mechanism: str | None = None  # e.g. "2 VOOR 5.00", "25% korting"
    price: float | None = None  # what you pay (with the offer, without a loyalty app)
    price_before: float | None = None
    member_price: float | None = None  # loyalty-app price, e.g. Lidl Plus
    member_label: str | None = None  # e.g. "met Lidl Plus"
    member_discount: str | None = None  # e.g. "-26%"

    def valid_on(self, day: date) -> bool:
        return self.start is not None and self.end is not None and self.start <= day <= self.end

    def overlaps(self, first: date, last: date) -> bool:
        return (self.start is not None and self.end is not None
                and self.start <= last and self.end >= first)


class Product(BaseModel):
    """A product from the AH app API search."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    webshop_id: int = Field(alias="webshopId")
    title: str
    main_category: str | None = Field(default=None, alias="mainCategory")
    sub_category: str | None = Field(default=None, alias="subCategory")
    brand: str | None = None
    sales_unit_size: str | None = Field(default=None, alias="salesUnitSize")
    is_bonus: bool = Field(default=False, alias="isBonus")
    promotion_type: str | None = Field(default=None, alias="promotionType")
    bonus_mechanism: str | None = Field(default=None, alias="bonusMechanism")
    bonus_start: date | None = Field(default=None, alias="bonusStartDate")
    bonus_end: date | None = Field(default=None, alias="bonusEndDate")
    price_before: float | None = Field(default=None, alias="priceBeforeBonus")
    price_now: float | None = Field(default=None, alias="currentPrice")

    @property
    def url(self) -> str:
        return f"https://www.ah.nl/producten/product/wi{self.webshop_id}"

    @property
    def in_store(self) -> bool:
        """NATIONAL = the in-store bonus; AHONLINE etc. are online-only deals."""
        return self.promotion_type == "NATIONAL"

    def valid_on(self, day: date) -> bool:
        return (
            self.bonus_start is not None
            and self.bonus_end is not None
            and self.bonus_start <= day <= self.bonus_end
        )

    def to_offer(self) -> Offer:
        # Without a bonus price AH only gives the regular price (e.g. "2 VOOR 5.00").
        now = self.price_now
        return Offer(
            store="ah",
            product_id=str(self.webshop_id),
            title=self.title,
            url=self.url,
            category=self.main_category,
            sub_category=self.sub_category,
            start=self.bonus_start,
            end=self.bonus_end,
            size=self.sales_unit_size,
            mechanism=self.bonus_mechanism or "bonus",
            price=now if now is not None else self.price_before,
            price_before=self.price_before if now is not None else None,
        )
