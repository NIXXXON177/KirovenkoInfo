#!/usr/bin/env python3
"""
Test script to debug description extraction for specific games.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Setup logging to see all details
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

sys.path.insert(0, str(Path(__file__).parent))

from src.donatov import (
    fetch_text,
    _extract_vue_resource,
    _game_description_from_resource,
    _html_to_plain,
    enrich_game_and_products,
)
from src.state_store import GameSnap
import aiohttp

log = logging.getLogger(__name__)


async def test_game_enrichment(game_id: int, game_url: str, game_name: str):
    """Test enrichment for a specific game."""
    print(f"\n{'='*60}")
    print(f"Testing Game: {game_name} (ID: {game_id})")
    print(f"URL: https://donatov.net{game_url}")
    print('='*60)
    
    game = GameSnap(
        id=game_id,
        name=game_name,
        url=game_url,
        cat_id=1,
        enabled=True,
        good_type=None,
        description=""
    )
    
    async with aiohttp.ClientSession() as session:
        enriched_game, products = await enrich_game_and_products(
            "https://donatov.net",
            session,
            45,
            game
        )
        
        print(f"\nResult:")
        print(f"  Type: {enriched_game.good_type}")
        print(f"  Description: {enriched_game.description[:100] if enriched_game.description else '(EMPTY)'}")
        if enriched_game.description:
            print(f"  Full length: {len(enriched_game.description)} characters")


async def main():
    games_to_test = [
        (472, "/anyverse", "AnyVerse"),
        (481, "/8-ball-pool", "8 Ball Pool"),
        (104, "/mobile-legends", "Mobile Legends"),
    ]
    
    for gid, url, name in games_to_test:
        try:
            await test_game_enrichment(gid, url, name)
        except Exception as e:
            print(f"\nERROR testing {name}: {e}")
            import traceback
            traceback.print_exc()
        
        # Small delay between requests
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
