from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ErrorEvent, Message
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import load_settings
from .games_ui import GamesListCb, games_list_text_and_keyboard
from .db_loader import build_snapshot_db_session
from .diff_events import diff_snapshots
from .donatov import build_snapshot, enrich_game_and_products
from .state_store import SiteSnapshot, load_snapshot, save_snapshot

log = logging.getLogger(__name__)
router = Router()


async def _telegram_with_retries(
    action,
    *,
    retries: int,
    label: str,
) -> None:
    delay = 5.0
    last: BaseException | None = None
    for i in range(retries):
        try:
            await action()
            return
        except TelegramNetworkError as e:
            last = e
            log.warning(
                "%s: нет связи с api.telegram.org (%s/%s): %s",
                label,
                i + 1,
                retries,
                e,
            )
            if i + 1 < retries:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)
    log.error(
        "Доступ к Telegram Bot API заблокирован или нестабилен (таймаут SSL / обрыв). "
        "Проверьте интернет, VPN или укажите TELEGRAM_PROXY в .env (см. .env.example)."
    )
    assert last is not None
    raise last


def _setup_logging(level: str, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)


async def _finalize_poll(bot: Bot, settings, snap: SiteSnapshot, src_label: str) -> None:
    old = load_snapshot(settings.state_path)
    events = diff_snapshots(old, snap)
    for ev in events:
        for chat_id in settings.chat_ids:
            await bot.send_message(chat_id, ev.text)
        log.info("Notify: %s", ev.text.replace("\n", " | "))
    save_snapshot(settings.state_path, snap)
    log.info(
        "Poll done (%s): categories=%d games=%d products=%d events=%d",
        src_label,
        len(snap.categories),
        len(snap.games),
        len(snap.products),
        len(events),
    )


async def _poll_once_site(bot: Bot, settings, session: aiohttp.ClientSession) -> None:
    base = await build_snapshot(settings.base_url, session, settings.request_timeout_sec)
    sem = asyncio.Semaphore(settings.fetch_concurrency)

    async def one(g):
        async with sem:
            return await enrich_game_and_products(
                settings.base_url,
                session,
                settings.request_timeout_sec,
                g,
            )

    games = list(base.games.values())
    pairs = await asyncio.gather(*[one(g) for g in games], return_exceptions=True)

    snap = base
    for i, result in enumerate(pairs):
        if isinstance(result, BaseException):
            log.error("Enrich failed for game %s: %s", games[i].id, result)
            continue
        g_new, prods = result
        snap.games[str(g_new.id)] = g_new
        for pid, p in prods.items():
            if pid in snap.products:
                prev = snap.products[pid]
                if prev.name != p.name or prev.price != p.price:
                    log.warning(
                        "Duplicate product id %s across games: keeping %r (was %r)",
                        pid,
                        p.name,
                        prev.name,
                    )
            snap.products[pid] = p

    await _finalize_poll(bot, settings, snap, "site")
    n_broker = sum(1 for g in snap.games.values() if g.good_type == "broker")
    if n_broker:
        log.info("Broker games (no JSON-LD list): %d", n_broker)


async def poll_loop_site(bot: Bot, settings) -> None:
    connector = aiohttp.TCPConnector(limit=settings.fetch_concurrency + 4)
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            try:
                await _poll_once_site(bot, settings, session)
            except Exception:
                log.exception("Poll iteration failed")
            await asyncio.sleep(settings.poll_interval_sec)


async def poll_loop_database(bot: Bot, settings) -> None:
    assert settings.db_config is not None
    cfg = settings.db_config
    engine = create_async_engine(cfg.url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        while True:
            try:
                async with factory() as session:
                    snap = await build_snapshot_db_session(session, cfg)
                await _finalize_poll(bot, settings, snap, "database")
            except Exception:
                log.exception("Poll iteration failed (database)")
            await asyncio.sleep(settings.poll_interval_sec)
    finally:
        await engine.dispose()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Бот мониторинга Donatov.net.\n"
        "Команды:\n"
        "/status — сводка по последнему снимку.\n"
        "/games — список игр по страницам.\n"
        "Первый успешный опрос сохраняет базу без уведомлений."
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Ваш chat id: {message.chat.id}")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    settings = load_settings()
    snap = load_snapshot(settings.state_path)
    if not snap:
        await message.answer("Снимок ещё не создан — дождитесь первого опроса.")
        return
    src = "БД" if settings.data_source == "database" else "сайт"
    await message.answer(
        f"Источник: {src}\n"
        f"Категории: {len(snap.categories)}\n"
        f"Игры: {len(snap.games)}\n"
        f"Товары: {len(snap.products)}\n"
        f"Интервал: {settings.poll_interval_sec} с"
    )


@router.message(Command("games"))
async def cmd_games(message: Message) -> None:
    settings = load_settings()
    snap = load_snapshot(settings.state_path)
    if not snap:
        await message.answer("Снимок ещё не создан — дождитесь первого опроса.")
        return
    text, kb = games_list_text_and_keyboard(settings, snap, page=0)
    await message.answer(text, reply_markup=kb)


@router.callback_query(GamesListCb.filter())
async def on_games_page(callback: CallbackQuery, callback_data: GamesListCb) -> None:
    settings = load_settings()
    snap = load_snapshot(settings.state_path)
    if not snap:
        await callback.answer("Снимок ещё не создан.", show_alert=True)
        return
    text, kb = games_list_text_and_keyboard(settings, snap, page=callback_data.page)
    if callback.message is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        log.exception("games list edit failed")
        await callback.answer("Не удалось обновить список.", show_alert=True)
        return
    await callback.answer()


async def main() -> None:
    settings = load_settings()
    log_path = Path(settings.state_path).parent
    _setup_logging(settings.log_level, log_path)

    session_kw: dict = {
        "timeout": settings.telegram_timeout_sec,
        "limit": 64,
    }
    if settings.telegram_proxy:
        session_kw["proxy"] = settings.telegram_proxy
        log.info("Используется TELEGRAM_PROXY для запросов к Bot API")
    session = AiohttpSession(**session_kw)
    bot = Bot(settings.bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(router)

    @dp.errors()
    async def log_errors(event: ErrorEvent) -> bool:
        exc = event.exception
        log.error(
            "Ошибка в обработчике: %s: %s",
            type(exc).__name__,
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return True

    async def delayed_poll_loop() -> None:
        await asyncio.sleep(2)
        if settings.data_source == "database":
            log.info("Режим DATA_SOURCE=database")
            await poll_loop_database(bot, settings)
        else:
            await poll_loop_site(bot, settings)

    poll_task: asyncio.Task[None] | None = None
    try:
        async def _clear_webhook() -> None:
            await bot.delete_webhook(drop_pending_updates=True)

        await _telegram_with_retries(
            _clear_webhook,
            retries=settings.telegram_api_retries,
            label="delete_webhook",
        )
        log.info("Webhook сброшен, включён long polling")
        poll_task = asyncio.create_task(delayed_poll_loop())
        await dp.start_polling(bot)
    finally:
        if poll_task is not None:
            poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poll_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
