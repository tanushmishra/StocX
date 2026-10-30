"""News fetching module for StocX AI Agents and Screener.

Fetches recent news and catalyst events for candidate tickers using:
1. Tavily Search API (primary if TAVILY_API_KEY is configured).
2. Yahoo Finance news feed via yfinance (fallback).

Never fabricates or mocks synthetic news headlines. If external sources
are unreachable, returns an empty list and logs the status clearly.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
try:
    import yfinance as yf
except ImportError:
    yf = None

import config

logger = logging.getLogger(__name__)

_TAVILY_API_URL = "https://api.tavily.com/search"
_PLACEHOLDER_KEYS = {
    "your_tavily_api_key_here",
    "placeholder",
    "dummy",
    "none",
    "null",
}


def is_valid_tavily_key(key: str | None) -> bool:
    """Check if a Tavily API key is provided and not a placeholder."""
    if not key or not isinstance(key, str):
        return False
    stripped = key.strip()
    if len(stripped) < 8:
        return False
    lowered = stripped.lower()
    if lowered in _PLACEHOLDER_KEYS or "your_" in lowered:
        return False
    return True


def fetch_tavily_news(ticker: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Fetch recent news for a ticker symbol using Tavily REST API.

    Args:
        ticker: Symbol (e.g. ``"INFY.NS"``).
        max_results: Max headline items to retrieve.

    Returns:
        List of standardized news dicts, or empty list on failure.
    """
    api_key = os.getenv("TAVILY_API_KEY") or getattr(config, "TAVILY_API_KEY", None)
    if not is_valid_tavily_key(api_key):
        return []

    clean_symbol = ticker.replace(".NS", "").replace(".BO", "")
    query = f"{clean_symbol} stock news earnings quarterly results management guidance"

    payload = {
        "api_key": str(api_key).strip(),
        "query": query,
        "search_depth": "news",
        "max_results": max_results,
    }

    try:
        resp = requests.post(_TAVILY_API_URL, json=payload, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_results = data.get("results", [])
            news_items = []
            for item in raw_results[:max_results]:
                news_items.append(
                    {
                        "title": item.get("title", "").strip(),
                        "publisher": item.get("domain", "") or "Tavily",
                        "url": item.get("url", ""),
                        "date": item.get("published_date", "") or "",
                        "snippet": item.get("content", "")[:200],
                        "source": "tavily",
                    }
                )
            if news_items:
                logger.info("Fetched %d Tavily news items for %s", len(news_items), ticker)
                return news_items
        else:
            logger.warning("Tavily search API returned HTTP %s for %s", resp.status_code, ticker)
    except Exception as exc:
        logger.warning("Failed to fetch Tavily news for %s: %s", ticker, exc)

    return []


def fetch_yfinance_news(ticker: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Fetch recent news for a ticker symbol using yfinance.

    Args:
        ticker: Symbol (e.g. ``"TCS.NS"``).
        max_results: Max headline items to retrieve.

    Returns:
        List of standardized news dicts, or empty list on failure.
    """
    if yf is None:
        return []

    try:
        tk = yf.Ticker(ticker)
        raw_news = tk.news or []
        news_items = []
        for item in raw_news[:max_results]:
            # yfinance news schema may vary between versions
            content = item.get("content", item)
            title = content.get("title", "")
            if not title:
                continue

            provider = (
                content.get("provider", {}).get("displayName")
                if isinstance(content.get("provider"), dict)
                else content.get("publisher", "Yahoo Finance")
            )
            url = (
                content.get("canonicalUrl", {}).get("url")
                if isinstance(content.get("canonicalUrl"), dict)
                else content.get("link", "")
            )
            pub_date = str(content.get("pubDate") or content.get("providerPublishTime") or "")

            news_items.append(
                {
                    "title": title.strip(),
                    "publisher": provider or "Yahoo Finance",
                    "url": url,
                    "date": pub_date,
                    "snippet": content.get("summary", "")[:200],
                    "source": "yfinance",
                }
            )

        if news_items:
            logger.info("Fetched %d yfinance news items for %s", len(news_items), ticker)
            return news_items
    except Exception as exc:
        logger.warning("Failed to fetch yfinance news for %s: %s", ticker, exc)

    return []


def fetch_ticker_news(ticker: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Fetch news from available providers in order of priority (Tavily -> yfinance).

    Never fabricates fake news. Returns [] if no real headlines are found.
    """
    # 1. Try Tavily
    items = fetch_tavily_news(ticker, max_results=max_results)
    if items:
        return items

    # 2. Fall back to yfinance
    items = fetch_yfinance_news(ticker, max_results=max_results)
    if items:
        return items

    logger.debug("No live news headlines found for %s", ticker)
    return []


def format_news_for_screener(ticker_news_map: dict[str, list[dict[str, Any]]]) -> str:
    """Format news headlines for inclusion in the Screener LLM prompt.

    Args:
        ticker_news_map: Mapping of ticker symbol to list of standardized news dicts.

    Returns:
        Markdown-formatted string summarizing recent headlines.
    """
    if not ticker_news_map:
        return "_No recent news or catalyst headlines available._"

    lines: list[str] = []
    has_any_news = False

    for ticker, items in ticker_news_map.items():
        if not items:
            continue
        has_any_news = True
        lines.append(f"### {ticker}")
        for item in items:
            title = item.get("title", "")
            publisher = item.get("publisher", "Unknown")
            date = item.get("date", "")
            meta = f" ({publisher}, {date})" if date else f" ({publisher})"
            lines.append(f"- **{title}**{meta}")
        lines.append("")

    if not has_any_news:
        return "_No live news headlines found for candidate tickers._"

    return "\n".join(lines).strip()
