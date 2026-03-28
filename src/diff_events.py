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


def _stock_label(ok: bool) -> str:
    return "в наличии" if ok else "нет в наличии"


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
                    text=f"📂 Новая категория\nНазвание: {c.name}\nID: {c.id}",
                    dedupe_key=f"cat+{cid}",
                )
            )
    
    for cid, c in old_c.items():
        if cid not in new_c:
            events.append(
                Event(
                    text=f"🔴 Категория удалена\nНазвание: {c.name}\nID: {c.id}",
                    dedupe_key=f"cat-{cid}",
                )
            )

    old_g, new_g = old.games, new.games
    
    for gid, g in new_g.items():
        if gid not in old_g:
            events.append(
                Event(
                    text=f"🎮 Новая игра\nНазвание: {g.name}\nID: {g.id}",
                    dedupe_key=f"game+{gid}",
                )
            )
    
    for gid, g in old_g.items():
        if gid not in new_g:
            events.append(
                Event(
                    text=f"🔴 Игра удалена\nНазвание: {g.name}\nID: {g.id}",
                    dedupe_key=f"game-{gid}",
                )
            )

    old_p, new_p = old.products, new.products
    
    for pid, p in new_p.items():
        if pid not in old_p:
            stock_line = (
                f"\n⚠️ {_stock_label(p.in_stock).capitalize()} на donatov.net"
                if not p.in_stock
                else ""
            )
            events.append(
                Event(
                    text=(
                        f"🟢 Новый товар\nНазвание: {p.name}\n"
                        f"Цена: {_fmt_rub(p.price)}{stock_line}\nID: {p.id}"
                    ),
                    dedupe_key=f"prod+{pid}",
                )
            )
    
    for pid, p in old_p.items():
        if pid not in new_p:
            events.append(
                Event(
                    text=f"🔴 Товар удалён\nНазвание: {p.name}\nID: {p.id}",
                    dedupe_key=f"prod-{pid}",
                )
            )

    for pid, p in new_p.items():
        if pid not in old_p:
            continue
        
        op = old_p[pid]
        price_changed = op.price != p.price
        name_changed = op.name != p.name
        desc_changed = (op.description or "") != (p.description or "")
        stock_changed = op.in_stock != p.in_stock
        
        if not price_changed and not name_changed and not desc_changed and not stock_changed:
            continue

        text_parts = [f"🟡 Товар изменён\nНазвание: {p.name}"]
        
        if price_changed:
            text_parts.append(f"Цена: {_fmt_rub(op.price)} → {_fmt_rub(p.price)}")
        
        if name_changed:
            text_parts.append(f"Название: {op.name} → {p.name}")
        
        if desc_changed:
            text_parts.append("Описание: изменено")
        
        if stock_changed:
            text_parts.append(
                f"Наличие: {_stock_label(op.in_stock)} → {_stock_label(p.in_stock)}"
            )
        
        text_parts.append(f"ID: {p.id}")
        text = "\n".join(text_parts)
        
        events.append(
            Event(
                text=text,
                dedupe_key=(
                    f"prod~{pid}_{_digest(p.name)}_{_digest(p.price)}_"
                    f"{_digest(p.description)}_{int(p.in_stock)}"
                ),
            )
        )

    return events
