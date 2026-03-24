from __future__ import annotations

import html as html_lib
import json
import logging
import re
from typing import Any

import aiohttp

from .state_store import CategorySnap, GameSnap, ProductSnap, SiteSnapshot

log = logging.getLogger(__name__)

GOOD_ID_RE = re.compile(r"/cover/good-(\d+)-", re.I)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _game_id_from_cover(cover: str | None) -> int | None:
    if not cover:
        return None
    m = GOOD_ID_RE.search(cover)
    return int(m.group(1)) if m else None


def _html_to_plain(html_s: str) -> str:
    if not html_s:
        return ""
    s = html_lib.unescape(html_s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(
        r"</(p|div|h[1-6]|li|tr|details|summary)\s*>",
        "\n",
        s,
        flags=re.I,
    )
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _game_description_from_resource(resource: dict[str, Any]) -> str:
    data = resource.get("data")
    if not isinstance(data, dict):
        log.debug("_game_description_from_resource: data is not dict")
        return ""
    html_d = str(data.get("description_html") or "").strip()
    if html_d:
        plain = _html_to_plain(html_d)
        if plain:
            log.debug("_game_description_from_resource: using description_html (%d chars)", len(plain))
            return plain
        else:
            log.debug("_game_description_from_resource: description_html is empty after parsing")
    short_d = str(data.get("short_description") or "").strip()
    if short_d:
        log.debug("_game_description_from_resource: using short_description (%d chars)", len(short_d))
        return short_d
    meta_d = str(data.get("meta_description") or "").strip()
    if meta_d:
        log.debug("_game_description_from_resource: using meta_description (%d chars)", len(meta_d))
    return meta_d


def _extract_vue_resource(html: str) -> dict[str, Any] | None:
    start = html.find('<vue-good-page')
    if start == -1:
        return None
    chunk = html[start:]
    key = ':resource="'
    j = chunk.find(key)
    if j == -1:
        return None
    j = start + j + len(key)
    rest = html[j:]
    end = rest.find('"></vue-good-page>')
    if end == -1:
        return None
    raw = html_lib.unescape(rest[:end])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.debug("vue-good-page JSON parse error: %s", e)
        return None


def _iter_ld_nodes(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        if "@graph" in obj:
            return [n for n in obj["@graph"] if isinstance(n, dict)]
        return [obj]
    return []


def _availability_in_stock(availability: str | None) -> bool:
    if not availability:
        return True
    return "InStock" in availability or "LimitedAvailability" in availability


def offers_from_ld_json(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<script\s+type="application/ld\+json"\s*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        raw = m.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_ld_nodes(data):
            offers = node.get("offers")
            if isinstance(offers, list):
                for o in offers:
                    if isinstance(o, dict) and o.get("@type") == "Offer":
                        out.append(o)
            elif isinstance(offers, dict) and offers.get("@type") == "Offer":
                out.append(offers)
    return out


def _sku_to_int(sku: str | None) -> int | None:
    if not sku or not isinstance(sku, str):
        return None
    sku = sku.strip().upper()
    if sku.startswith("P") and sku[1:].isdigit():
        return int(sku[1:])
    if sku.isdigit():
        return int(sku)
    return None


def products_from_offers(offers: list[dict[str, Any]]) -> dict[str, ProductSnap]:
    products: dict[str, ProductSnap] = {}
    for o in offers:
        sku = o.get("sku")
        pid = _sku_to_int(sku)
        if pid is None:
            continue
        name = str(o.get("name") or "").strip() or f"#{pid}"
        price = str(o.get("price") or "").strip() or "—"
        in_stock = _availability_in_stock(str(o.get("availability") or ""))
        key = str(pid)
        products[key] = ProductSnap(
            id=pid, name=name, price=price, in_stock=in_stock, description=""
        )
    return products


async def fetch_text(session: aiohttp.ClientSession, url: str, timeout: int) -> str:
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
    ) as resp:
        resp.raise_for_status()
        return await resp.text()


async def fetch_json(session: aiohttp.ClientSession, url: str, timeout: int) -> Any:
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def build_snapshot(base_url: str, session: aiohttp.ClientSession, timeout: int) -> SiteSnapshot:
    list_url = f"{base_url}/good/list/json"
    payload = await fetch_json(session, list_url, timeout)
    data = payload.get("data") or {}

    snap = SiteSnapshot()

    for c in data.get("cats") or []:
        if not isinstance(c, dict):
            continue
        cid = int(c["id"])
        key = str(cid)
        snap.categories[key] = CategorySnap(
            id=cid,
            name=str(c.get("name") or ""),
            slug=str(c.get("slug") or ""),
        )

    for item in data.get("catalog") or []:
        if not isinstance(item, dict):
            continue
        gid = _game_id_from_cover(item.get("cover"))
        if gid is None:
            log.warning("Catalog row without good-* id in cover, skipped: %s", item.get("url"))
            continue
        url_path = str(item.get("url") or "")
        if not url_path.startswith("/"):
            url_path = "/" + url_path
        cat_id = item.get("cat_id")
        snap.games[str(gid)] = GameSnap(
            id=gid,
            name=str(item.get("name") or ""),
            url=url_path,
            cat_id=int(cat_id) if cat_id is not None else None,
            enabled=True,
            good_type=None,
            description="",
        )

    return snap


async def enrich_game_and_products(
    base_url: str,
    session: aiohttp.ClientSession,
    timeout: int,
    game: GameSnap,
) -> tuple[GameSnap, dict[str, ProductSnap]]:
    url = f"{base_url}{game.url}"
    log.debug("Enriching game %d: %s", game.id, url)
    try:
        html = await fetch_text(session, url, timeout)
        log.debug("Game %d: fetched %d bytes of HTML", game.id, len(html))
    except Exception as e:
        log.warning("Failed to fetch game page %s: %s", url, e)
        return game, {}

    resource = _extract_vue_resource(html)
    enabled = game.enabled
    good_type = game.good_type
    name = game.name
    description = ""

    if resource:
        log.debug("Game %d: Found vue resource", game.id)
        g = resource.get("good") or {}
        if isinstance(g, dict):
            if "enabled" in g:
                enabled = bool(g["enabled"])
            good_type = str(g.get("type") or good_type or "")
            name = str(g.get("name") or name)

        description = _game_description_from_resource(resource)
        if description:
            log.info("Game %d: description from resource (vue): %d chars", game.id, len(description))
        else:
            log.debug("Game %d: vue resource found but no description extracted", game.id)
    else:
        log.debug("Game %d: No vue resource found in HTML", game.id)

    if not description:
        m = re.search(
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            html,
            re.S | re.I,
        )
        if m:
            description = _html_to_plain(m.group(1))
            if description:
                log.info("Game %d: description from content div: %d chars", game.id, len(description))
            else:
                log.debug("Game %d: content div found but empty after parsing", game.id)
        else:
            log.debug("Game %d: no content div found", game.id)

    if not description:
        m = re.search(
            r'<meta\s+name="description"\s+content="([^"]*)"',
            html,
            re.I,
        )
        if m:
            description = html_lib.unescape(m.group(1)).strip()
            if description:
                log.info("Game %d: description from meta: %d chars", game.id, len(description))
            else:
                log.debug("Game %d: meta description found but empty", game.id)
        else:
            log.debug("Game %d: no meta description found", game.id)

    if not description:
        m = re.search(
            r'<article[^>]*>(.*?)</article>|<section[^>]*>(.*?)</section>',
            html,
            re.S | re.I,
        )
        if m:
            desc_html = m.group(1) or m.group(2)
            description = _html_to_plain(desc_html)
            if description:
                log.info("Game %d: description from article/section: %d chars", game.id, len(description))
            else:
                log.debug("Game %d: article/section found but empty after parsing", game.id)
        else:
            log.debug("Game %d: no article/section found", game.id)

    if not description:
        m = re.search(
            r'<h1[^>]*>.*?</h1>(.*?)(?:<h2|<footer|<script|$)',
            html,
            re.S | re.I,
        )
        if m:
            description = _html_to_plain(m.group(1))
            if description:
                log.info("Game %d: description from h1 context: %d chars", game.id, len(description))
            else:
                log.debug("Game %d: h1 context found but empty after parsing", game.id)
        else:
            log.debug("Game %d: no h1 context found", game.id)

    if not description:
        m = re.search(
            r'<meta\s+property="og:description"\s+content="([^"]*)"',
            html,
            re.I,
        )
        if m:
            description = html_lib.unescape(m.group(1)).strip()
            if description:
                log.info("Game %d: description from og:description: %d chars", game.id, len(description))
            else:
                log.debug("Game %d: og:description found but empty", game.id)
        else:
            log.debug("Game %d: no og:description found", game.id)

    if not description:
        log.warning("Game %d (%s): no description extracted from %s", game.id, game.name, url)

    updated = GameSnap(
        id=game.id,
        name=name,
        url=game.url,
        cat_id=game.cat_id,
        enabled=enabled,
        good_type=good_type,
        description=description,
    )

    products: dict[str, ProductSnap] = {}
    if good_type == "pack":
        offers = offers_from_ld_json(html)
        products = products_from_offers(offers)
    elif good_type == "broker":
        log.info("Game %s is broker type — offers are not in JSON-LD; products skipped", game.id)
    else:
        offers = offers_from_ld_json(html)
        if offers:
            products = products_from_offers(offers)

    return updated, products
