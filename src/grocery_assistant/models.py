"""Products as returned by the AH app API, validated with pydantic.

Only the fields we use are declared; everything else in the response is
ignored, so new AH fields don't break anything. A missing or renamed field we
do use fails validation with a clear error.
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Product(BaseModel):
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
