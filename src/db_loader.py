from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db_config import DbSourceConfig
from .state_store import CategorySnap, GameSnap, ProductSnap, SiteSnapshot

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _qi(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _coerce_bool(val) -> bool:
    if val is None:
        return True
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    if s in ("0", "false", "no", ""):
        return False
    return True


def _price_str(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, Decimal):
        s = format(val, "f").rstrip("0").rstrip(".")
        return s or "0"
    return str(val).strip() or "—"


async def build_snapshot_db_session(session: AsyncSession, cfg: DbSourceConfig) -> SiteSnapshot:
    snap = SiteSnapshot()

    t = _qi(cfg.categories_table)
    cid, cname = _qi(cfg.cat_id), _qi(cfg.cat_name)
    if cfg.cat_slug:
        slug_sel = f"COALESCE({_qi(cfg.cat_slug)}, '')"
    else:
        slug_sel = "''"
    wcat = ""
    if cfg.cat_deleted_at:
        wcat = f" WHERE {_qi(cfg.cat_deleted_at)} IS NULL"
    sql_cat = text(f"SELECT {cid} AS id, {cname} AS name, {slug_sel} AS slug FROM {t}{wcat}")
    res = await session.execute(sql_cat)
    for row in res.mappings():
        i = int(row["id"])
        snap.categories[str(i)] = CategorySnap(
            id=i,
            name=str(row["name"] or ""),
            slug=str(row["slug"] or ""),
        )

    tg = _qi(cfg.games_table)
    gid, gname = _qi(cfg.game_id), _qi(cfg.game_name)
    if cfg.game_enabled:
        ens = f"{_qi(cfg.game_enabled)} AS g_en"
    else:
        ens = "NULL AS g_en"
    if cfg.game_description:
        gdesc = f"{_qi(cfg.game_description)} AS g_desc"
    else:
        gdesc = "'' AS g_desc"
    wgame = ""
    if cfg.game_deleted_at:
        wgame = f" WHERE {_qi(cfg.game_deleted_at)} IS NULL"
    sql_game = text(
        f"SELECT {gid} AS id, {gname} AS name, {ens}, {gdesc} FROM {tg}{wgame}"
    )
    res = await session.execute(sql_game)
    for row in res.mappings():
        i = int(row["id"])
        gd = row["g_desc"]
        desc_s = str(gd) if gd is not None else ""
        snap.games[str(i)] = GameSnap(
            id=i,
            name=str(row["name"] or ""),
            url=f"/g/{i}",
            cat_id=None,
            enabled=_coerce_bool(row["g_en"]),
            good_type="db",
            description=desc_s,
        )

    tp = _qi(cfg.products_table)
    pid, pname, pprice = _qi(cfg.product_id), _qi(cfg.product_name), _qi(cfg.product_price)
    if cfg.product_description:
        dsel = f"{_qi(cfg.product_description)} AS p_desc"
    else:
        dsel = "'' AS p_desc"
    if cfg.product_in_stock:
        ssel = f"{_qi(cfg.product_in_stock)} AS p_st"
    else:
        ssel = "NULL AS p_st"
    wprod = ""
    if cfg.product_deleted_at:
        wprod = f" WHERE {_qi(cfg.product_deleted_at)} IS NULL"
    sql_prod = text(
        f"SELECT {pid} AS id, {pname} AS name, {pprice} AS price, {dsel}, {ssel} FROM {tp}{wprod}"
    )
    res = await session.execute(sql_prod)
    for row in res.mappings():
        i = int(row["id"])
        desc = row["p_desc"]
        desc_s = str(desc) if desc is not None else ""
        snap.products[str(i)] = ProductSnap(
            id=i,
            name=str(row["name"] or "").strip() or f"#{i}",
            price=_price_str(row["price"]),
            in_stock=_coerce_bool(row["p_st"]),
            description=desc_s,
        )

    return snap
