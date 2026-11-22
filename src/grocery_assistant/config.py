"""Settings (environment) and the query definitions (queries.yaml)."""
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment; prefix GA_ (e.g. GA_CONFIG, GA_LOG_LEVEL)."""

    model_config = SettingsConfigDict(env_prefix="GA_")

    config: Path = Path("config/queries.yaml")
    log_level: str = "INFO"
    tz: str = Field(default="Europe/Amsterdam", validation_alias="TZ")


class Category(BaseModel):
    id: int
    main_category: str
    label: str


class Query(BaseModel):
    name: str
    title: str
    store: Literal["ah"] = "ah"
    schedule: str
    webhook: str
    in_store_only: bool = True
    categories: list[Category]


class QueryFile(BaseModel):
    queries: list[Query]


def load_queries(path: Path) -> dict[str, Query]:
    data = QueryFile.model_validate(yaml.safe_load(path.read_text()))
    names = [q.name for q in data.queries]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate query names in {path}")
    return {q.name: q for q in data.queries}
