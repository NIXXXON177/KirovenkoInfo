from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(key: str, default: str) -> str:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip()


def _env_opt(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key)
    if v is None:
        return default
    s = v.strip()
    return s if s else None


@dataclass(frozen=True)
class DbSourceConfig:
    url: str
    categories_table: str
    games_table: str
    products_table: str
    cat_id: str
    cat_name: str
    cat_slug: str | None
    cat_deleted_at: str | None
    game_id: str
    game_name: str
    game_enabled: str | None
    game_deleted_at: str | None
    product_id: str
    product_name: str
    product_price: str
    product_description: str | None
    product_in_stock: str | None
    product_deleted_at: str | None


def load_db_source_config() -> DbSourceConfig:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required when DATA_SOURCE=database")
    return DbSourceConfig(
        url=url,
        categories_table=_env_str("DB_TABLE_CATEGORIES", "categories"),
        games_table=_env_str("DB_TABLE_GAMES", "games"),
        products_table=_env_str("DB_TABLE_PRODUCTS", "products"),
        cat_id=_env_str("DB_CAT_ID", "id"),
        cat_name=_env_str("DB_CAT_NAME", "name"),
        cat_slug=_env_opt("DB_CAT_SLUG", "slug"),
        cat_deleted_at=_env_opt("DB_CAT_DELETED_AT"),
        game_id=_env_str("DB_GAME_ID", "id"),
        game_name=_env_str("DB_GAME_NAME", "name"),
        game_enabled=_env_opt("DB_GAME_ENABLED", "enabled"),
        game_deleted_at=_env_opt("DB_GAME_DELETED_AT"),
        product_id=_env_str("DB_PRODUCT_ID", "id"),
        product_name=_env_str("DB_PRODUCT_NAME", "name"),
        product_price=_env_str("DB_PRODUCT_PRICE", "price"),
        product_description=_env_opt("DB_PRODUCT_DESCRIPTION", "description"),
        product_in_stock=_env_opt("DB_PRODUCT_IN_STOCK"),
        product_deleted_at=_env_opt("DB_PRODUCT_DELETED_AT"),
    )
