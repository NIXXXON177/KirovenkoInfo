from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Settings
from .state_store import GameSnap, SiteSnapshot

PAGE_SIZE = 12


class GamesListCb(CallbackData, prefix="gl"):
    page: int


def _line(settings: Settings, g: GameSnap) -> str:
    st = "✓" if g.enabled else "✗"
    u = (g.url or "").strip()
    if u.startswith("/"):
        link = f"{settings.base_url}{u}"
        return f"{st} ID {g.id} — {g.name}\n{link}"
    return f"{st} ID {g.id} — {g.name}"


def games_list_text_and_keyboard(
    settings: Settings,
    snap: SiteSnapshot,
    page: int,
) -> tuple[str, InlineKeyboardMarkup | None]:
    games = sorted(snap.games.values(), key=lambda x: (x.name or "").lower())
    n = len(games)
    if n == 0:
        return "В снимке пока нет игр.", None

    total_pages = max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = games[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    header = f"🎮 Игры: всего {n}, страница {page + 1} из {total_pages}\n\n"
    body = "\n\n".join(_line(settings, g) for g in chunk)
    text = header + body

    if len(text) > 4000:
        short_chunk = chunk[: max(1, len(chunk) // 2)]
        body = "\n\n".join(_line(settings, g) for g in short_chunk)
        text = header + body + "\n\n… сокращено (слишком длинные названия)."

    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="« Назад",
                callback_data=GamesListCb(page=page - 1).pack(),
            )
        )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="Вперёд »",
                callback_data=GamesListCb(page=page + 1).pack(),
            )
        )
    if nav:
        rows.append(nav)

    return text, InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
