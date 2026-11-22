"""Settings (environment) and the query definitions (queries.yaml)."""
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment; prefix GA_ (e.g. GA_CONFIG, GA_LOG_LEVEL)."""

    model_config = SettingsConfigDict(env_prefix="GA_")

    config: Path = Path("config/queries.yaml")
    log_level: str = "INFO"
    tz: str = Field(default="Europe/Amsterdam", validation_alias="TZ")


class Category(BaseModel):
    label: str  # section heading in the post
    match: list[str]  # the store's category names that belong in this section
    id: int | None = None  # AH only: top-level taxonomyId to search


class Query(BaseModel):
    name: str
    title: str
    store: Literal["ah", "lidl"]
    schedule: str
    webhook: str
    # day: offers valid on the run date. week: offers running at any point in the
    # 7 days from the run date (Lidl's Thursday offers on a Monday run).
    window: Literal["day", "week"] = "day"
    in_store_only: bool = True  # AH: only the in-store (NATIONAL) bonus
    categories: list[Category]

    @model_validator(mode="after")
    def _ah_needs_ids(self) -> "Query":
        if self.store == "ah" and any(c.id is None for c in self.categories):
            raise ValueError(f"{self.name}: every AH category needs an id (taxonomyId)")
        return self


class QueryFile(BaseModel):
    queries: list[Query]


def load_queries(path: Path) -> dict[str, Query]:
    data = QueryFile.model_validate(yaml.safe_load(path.read_text()))
    names = [q.name for q in data.queries]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate query names in {path}")
    return {q.name: q for q in data.queries}
