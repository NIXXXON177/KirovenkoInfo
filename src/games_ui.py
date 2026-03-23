from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Settings
from .state_store import GameSnap, SiteSnapshot

PAGE_SIZE = 10
PREVIEW_CHARS = 120
MSG_SOFT_LIMIT = 4000


class GamesListCb(CallbackData, prefix="gl"):
    page: int


def split_telegram_chunks(text: str, limit: int = MSG_SOFT_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip()
    return chunks


def _preview(desc: str, n: int) -> str:
    d = (desc or "").strip().replace("\n", " ")
    if not d:
        return ""
    if len(d) <= n:
        return d
    return d[: n - 1].rstrip() + "…"


def _line(settings: Settings, g: GameSnap) -> str:
    st = "✓" if g.enabled else "✗"
    u = (g.url or "").strip()
    lines = [f"{st} ID {g.id} — {g.name}"]
    if u.startswith("/"):
        lines.append(f"{settings.base_url}{u}")
    pv = _preview(g.description, PREVIEW_CHARS)
    if pv:
        lines.append(f"Описание: {pv}")
        lines.append(f"Полный текст (если длинное): /game {g.id}")
    else:
        lines.append(
            "Описание в снимке пустое (после опроса подтянется). "
            f"Полный текст: /game {g.id}"
        )
    return "\n".join(lines)


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

    header = (
        f"🎮 Игры: всего {n}, страница {page + 1} из {total_pages}\n"
        f"Полное описание игры: /game и ID (число в строке «ID …»).\n\n"
    )
    body = "\n\n".join(_line(settings, g) for g in chunk)
    text = header + body

    if len(text) > MSG_SOFT_LIMIT:
        short_chunk = chunk[: max(1, len(chunk) // 2)]
        body = "\n\n".join(_line(settings, g) for g in short_chunk)
        text = header + body + "\n\n… сокращено: откройте /games и листайте страницы."

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


def format_game_detail_chunks(
    settings: Settings,
    snap: SiteSnapshot,
    game_id: int,
) -> list[str] | None:
    g = snap.games.get(str(game_id))
    if g is None:
        return None
    head = [
        f"🎮 {g.name}",
        f"ID: {g.id}  {'✓ активна' if g.enabled else '✗ неактивна'}",
    ]
    if g.good_type:
        head.append(f"Тип: {g.good_type}")
    u = (g.url or "").strip()
    if u.startswith("/"):
        head.append(f"{settings.base_url}{u}")
    body = "\n".join(head)
    desc = (g.description or "").strip()
    if not desc:
        return [
            body
            + "\n\nОписание пока пустое в снимке. После следующего опроса страницы игры текст появится."
        ]
    full = body + "\n\n────────\nОписание:\n" + desc
    return split_telegram_chunks(full)
