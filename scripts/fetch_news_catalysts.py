"""
News & Catalyst Helper Module for StocX Multi-Agent System.
Author: Anay Tiwari (Data Engineer)

Provides genuine macroeconomic headlines and catalysts for Dhairya's Screener
and CRO Reporting agents without modifying their core modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
HEADLINES_FILE = DATA_DIR / "historical_regime_headlines.json"


def get_regime_headlines(regime_key: str) -> list[dict[str, str]]:
    """Retrieve authentic historical headlines for a given stress regime.

    Args:
        regime_key: Key in config.CRASH_REGIMES (e.g. 'COVID_2020', 'ELECTION_2024')

    Returns:
        List of headline dictionaries with keys: date, source, title, impact.
    """
    if not HEADLINES_FILE.exists():
        return []

    with open(HEADLINES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    regimes = data.get("regimes", {})
    if regime_key in regimes:
        return regimes[regime_key].get("headlines", [])
    return []


def format_headlines_for_prompt(regime_key: str) -> str:
    """Format regime headlines into a markdown summary for LLM context injection."""
    headlines = get_regime_headlines(regime_key)
    if not headlines:
        return "_No historical headlines available for this regime._"

    lines = [f"### 📰 Macroeconomic News Catalysts ({regime_key})"]
    for h in headlines:
        lines.append(f"- **{h['date']}** [{h['source']}]: *\"{h['title']}\"* — {h['impact']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Testing News Catalyst Module...")
    for r in ["COVID_2020", "ELECTION_2024", "TECH_SELLOFF_2022", "2008_GFC"]:
        items = get_regime_headlines(r)
        print(f"{r}: {len(items)} headlines available.")
        if items:
            print("  Sample:", items[0]["title"], f"({items[0]['source']})")
