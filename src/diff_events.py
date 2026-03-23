from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from .state_store import SiteSnapshot

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    text: str
    dedupe_key: str


def _digest(s: str) -> str:
    return hashlib.md5(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def _fmt_rub(price: str) -> str:
    p = price.strip()
    if p == "—" or not p:
        return "—"
    return f"{p}₽"


def diff_snapshots(old: SiteSnapshot | None, new: SiteSnapshot) -> list[Event]:
    events: list[Event] = []
    if old is None:
        log.info("Baseline saved: no notifications for this run")
        return events

    old_c, new_c = old.categories, new.categories
    for cid, c in new_c.items():
        if cid not in old_c:
            events.append(
                Event(
                    text=f"📂 Новая категория Название: {c.name} ID: {c.id}",
                    dedupe_key=f"cat+{cid}",
                )
            )
    for cid, c in old_c.items():
        if cid not in new_c:
            events.append(
                Event(
                    text=f"🔴 Категория удалена Название: {c.name} ID: {c.id}",
                    dedupe_key=f"cat-{cid}",
                )
            )

    old_g, new_g = old.games, new.games
    for gid, g in new_g.items():
        if gid not in old_g:
            events.append(
                Event(
                    text=f"🎮 Новая игра Название: {g.name} ID: {g.id}",
                    dedupe_key=f"game+{gid}",
                )
            )
            continue
        og = old_g[gid]
        if og.enabled and not g.enabled:
            events.append(
                Event(
                    text=f"🟠 Игра неактивна (отключена) Название: {g.name} ID: {g.id}",
                    dedupe_key=f"game_off_{gid}",
                )
            )
        elif not og.enabled and g.enabled:
            events.append(
                Event(
                    text=f"🟢 Игра снова активна Название: {g.name} ID: {g.id}",
                    dedupe_key=f"game_on_{gid}",
                )
            )
        if og.name != g.name:
            events.append(
                Event(
                    text=f"🟡 Игра переименована 🆔 ID: {g.id}\nБыло: {og.name}\nСтало: {g.name}",
                    dedupe_key=f"game_name_{gid}_{hash(g.name)}",
                )
            )
        if (og.description or "") != (g.description or ""):
            events.append(
                Event(
                    text=f"🟡 Изменено описание игры 🎮 {g.name} 🆔 ID: {g.id}",
                    dedupe_key=f"game_desc_{gid}_{_digest(g.description)}",
                )
            )

    for gid, g in old_g.items():
        if gid not in new_g:
            events.append(
                Event(
                    text=f"🔴 Игра удалена Название: {g.name} ID: {g.id}",
                    dedupe_key=f"game-{gid}",
                )
            )

    old_p, new_p = old.products, new.products
    for pid, p in new_p.items():
        if pid not in old_p:
            events.append(
                Event(
                    text=(
                        f"🟢 Новый товар 📦 Название: {p.name} "
                        f"💰 Цена: {_fmt_rub(p.price)} 🆔 ID: {p.id}"
                    ),
                    dedupe_key=f"prod+{pid}",
                )
            )
            continue
        op = old_p[pid]
        price_changed = op.price != p.price
        name_changed = op.name != p.name
        stock_changed = op.in_stock != p.in_stock
        desc_changed = (op.description or "") != (p.description or "")
        if not price_changed and not name_changed and not stock_changed and not desc_changed:
            continue

        parts: list[str] = []
        if price_changed:
            parts.append(
                f"🟡 Товар изменён 📦 Название: {p.name} "
                f"💰 Было: {_fmt_rub(op.price)} 💰 Стало: {_fmt_rub(p.price)}"
            )
        elif name_changed or stock_changed or desc_changed:
            parts.append(f"🟡 Товар изменён 📦 Название: {p.name} 🆔 ID: {p.id}")
        extras: list[str] = []
        if name_changed and price_changed:
            extras.append(f"📝 Название было: {op.name}")
        elif name_changed and not price_changed:
            extras.append(f"📝 Название было: {op.name} → стало: {p.name}")
        if stock_changed:
            was = "в наличии" if op.in_stock else "нет в наличии"
            now = "в наличии" if p.in_stock else "нет в наличии"
            extras.append(f"📦 Наличие: было {was}, стало {now}")
        if desc_changed:
            extras.append("📝 Описание изменено")
        text = "\n".join(parts + extras)
        events.append(
            Event(
                text=text,
                dedupe_key=f"prod~{pid}_{p.name}_{p.price}_{p.in_stock}_{_digest(p.description)}",
            )
        )

    for pid, p in old_p.items():
        if pid not in new_p:
            events.append(
                Event(
                    text=f"🔴 Товар удалён 📦 Название: {p.name} 🆔 ID: {p.id}",
                    dedupe_key=f"prod-{pid}",
                )
            )

    return events
