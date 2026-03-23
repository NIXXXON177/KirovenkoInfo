from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STATE_VERSION = 1


@dataclass
class CategorySnap:
    id: int
    name: str
    slug: str


@dataclass
class GameSnap:
    id: int
    name: str
    url: str
    cat_id: int | None
    enabled: bool
    good_type: str | None = None
    description: str = ""


@dataclass
class ProductSnap:
    id: int
    name: str
    price: str
    in_stock: bool
    description: str = ""


@dataclass
class SiteSnapshot:
    categories: dict[str, CategorySnap] = field(default_factory=dict)
    games: dict[str, GameSnap] = field(default_factory=dict)
    products: dict[str, ProductSnap] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "categories": {k: asdict(v) for k, v in self.categories.items()},
            "games": {k: asdict(v) for k, v in self.games.items()},
            "products": {k: asdict(v) for k, v in self.products.items()},
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> SiteSnapshot:
        snap = cls()
        for cid, c in data.get("categories", {}).items():
            snap.categories[cid] = CategorySnap(
                id=int(c["id"]),
                name=c["name"],
                slug=c.get("slug", ""),
            )
        for gid, g in data.get("games", {}).items():
            snap.games[gid] = GameSnap(
                id=int(g["id"]),
                name=g["name"],
                url=g.get("url", ""),
                cat_id=g.get("cat_id"),
                enabled=g.get("enabled", True),
                good_type=g.get("good_type"),
                description=str(g.get("description") or ""),
            )
        for pid, p in data.get("products", {}).items():
            snap.products[pid] = ProductSnap(
                id=int(p["id"]),
                name=p["name"],
                price=p["price"],
                in_stock=p.get("in_stock", True),
                description=p.get("description", ""),
            )
        return snap


def load_snapshot(path: str) -> SiteSnapshot | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("version") != STATE_VERSION:
            log.warning("State file version mismatch, starting fresh baseline")
            return None
        return SiteSnapshot.from_json_dict(data)
    except (json.JSONDecodeError, OSError, TypeError) as e:
        log.error("Failed to load state from %s: %s", path, e)
        return None


def save_snapshot(path: str, snapshot: SiteSnapshot) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    payload = json.dumps(snapshot.to_json_dict(), ensure_ascii=False, indent=2)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(p)
