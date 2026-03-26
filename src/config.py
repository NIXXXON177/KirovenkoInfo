import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .db_config import DbSourceConfig, load_db_source_config

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    chat_ids: tuple[int, ...]
    poll_interval_sec: int
    base_url: str
    state_path: str
    log_level: str
    data_source: str
    db_config: DbSourceConfig | None
    fetch_concurrency: int = 8
    request_timeout_sec: int = 45
    telegram_proxy: str | None = None
    telegram_timeout_sec: float = 120.0
    telegram_api_retries: int = 5
    no_changes_sticker_file_id: str | None = None
    no_changes_sticker_cooldown_sec: int = 3600
    no_changes_custom_emoji_id: str | None = None
    no_changes_quiet_text: str = "Без изменений на сайте."
    no_changes_custom_emoji_fallback: str = "✅"


def _parse_chat_ids(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return tuple(int(p) for p in parts)


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    chats = os.getenv("CHAT_IDS", "").strip()
    if not chats:
        raise RuntimeError("CHAT_IDS is not set")

    raw_state = os.getenv("STATE_PATH", "./data/state.json").strip()
    state_p = Path(raw_state)
    if not state_p.is_absolute():
        state_p = _PROJECT_ROOT / state_p

    proxy = os.getenv("TELEGRAM_PROXY", "").strip()
    data_source = os.getenv("DATA_SOURCE", "site").strip().lower()
    if data_source not in ("site", "database"):
        raise RuntimeError("DATA_SOURCE must be site or database")

    db_cfg: DbSourceConfig | None = None
    if data_source == "database":
        db_cfg = load_db_source_config()

    quiet_sticker = os.getenv("NO_CHANGES_STICKER_FILE_ID", "").strip()
    quiet_cooldown = int(os.getenv("NO_CHANGES_STICKER_COOLDOWN_SEC", "3600"))
    quiet_emoji = os.getenv("NO_CHANGES_CUSTOM_EMOJI_ID", "").strip()
    quiet_msg = os.getenv("NO_CHANGES_QUIET_TEXT", "Без изменений на сайте.").strip()
    quiet_fb = os.getenv("NO_CHANGES_CUSTOM_EMOJI_FALLBACK", "✅").strip() or "✅"

    return Settings(
        bot_token=token,
        chat_ids=_parse_chat_ids(chats),
        poll_interval_sec=int(os.getenv("POLL_INTERVAL_SEC", "120")),
        base_url=os.getenv("BASE_URL", "https://donatov.net").rstrip("/"),
        state_path=str(state_p),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        data_source=data_source,
        db_config=db_cfg,
        fetch_concurrency=int(os.getenv("FETCH_CONCURRENCY", "8")),
        request_timeout_sec=int(os.getenv("REQUEST_TIMEOUT_SEC", "45")),
        telegram_proxy=proxy or None,
        telegram_timeout_sec=float(os.getenv("TELEGRAM_TIMEOUT_SEC", "120")),
        telegram_api_retries=int(os.getenv("TELEGRAM_API_RETRIES", "5")),
        no_changes_sticker_file_id=quiet_sticker or None,
        no_changes_sticker_cooldown_sec=max(0, quiet_cooldown),
        no_changes_custom_emoji_id=quiet_emoji or None,
        no_changes_quiet_text=quiet_msg or "Без изменений на сайте.",
        no_changes_custom_emoji_fallback=quiet_fb,
    )
