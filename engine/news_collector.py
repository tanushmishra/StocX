"""Financial News Intelligence Engine for the Market-Neutral Hedge Builder.

This module provides multi-source financial news collection for NSE-listed equities
using Tavily, Google News RSS, and Yahoo Finance. All collected headlines are
validated against a strict zero-hallucination Pydantic schema, deduplicated across
providers, normalized to ISO-8601 UTC timestamps, and cached for consumption by
the Screener Agent and Streamlit dashboard.

Invariants:
-----------
- Never invent headlines, dates, URLs, or sentiment scores.
- Missing values remain None (null in JSON).
- Provider failures are handled independently; a failure in one provider never
  crashes the entire pipeline.
- Timestamps are normalized to ISO-8601 UTC strings when parseable.
"""

from __future__ import annotations

import email.utils
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Set

import requests
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Paths and Cache Configuration
# ────────────────────────────────────────────────────────────────────────────

try:
    from config import DATA_CACHE_DIR  # type: ignore[import-untyped]
    _CACHE_DIR = Path(DATA_CACHE_DIR)
except Exception:
    _CACHE_DIR = Path("data_cache")

_HEADLINES_CACHE_FILE = _CACHE_DIR / "headlines.json"
_NEWS_SNAPSHOTS_DIR = _CACHE_DIR / "news"

# ────────────────────────────────────────────────────────────────────────────
# Target Stock Metadata (NSE Equities)
# ────────────────────────────────────────────────────────────────────────────

NSE_COMPANY_NAMES: Dict[str, str] = {
    "TCS.NS": "Tata Consultancy Services",
    "INFY.NS": "Infosys",
    "WIPRO.NS": "Wipro",
    "HCLTECH.NS": "HCL Technologies",
    "TECHM.NS": "Tech Mahindra",
    "LTIM.NS": "LTIMindtree",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "AXISBANK.NS": "Axis Bank",
    "SBIN.NS": "State Bank of India",
    "MARUTI.NS": "Maruti Suzuki",
    "SUNPHARMA.NS": "Sun Pharma",
    "RELIANCE.NS": "Reliance Industries",
}


# ────────────────────────────────────────────────────────────────────────────
# Standardized News Schema
# ────────────────────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    """Standardized representation of a single company news article.

    Attributes:
        ticker: NSE ticker symbol with suffix (e.g. 'TCS.NS').
        headline: Verbatim news headline extracted from the source.
        source: Name of the publishing outlet (e.g. 'Moneycontrol', 'Reuters').
        published_at: ISO-8601 UTC timestamp string, or None if unavailable.
        url: Canonical web link to the article, or None if unavailable.
        provider: Provider identifier ('tavily', 'google_news', 'yfinance').
        snippet: Verbatim article description or summary, or None if unavailable.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ticker: str = Field(description="NSE ticker symbol with .NS suffix")
    headline: str = Field(description="Original headline text from the publisher")
    source: str = Field(description="Publisher or publication name")
    published_at: Optional[str] = Field(default=None, description="ISO-8601 UTC timestamp or None")
    url: Optional[str] = Field(default=None, description="Article URL or None")
    provider: Literal["tavily", "google_news", "yfinance"] = Field(
        description="Source provider engine"
    )
    snippet: Optional[str] = Field(default=None, description="Article excerpt/description or None")

    @field_validator("headline")
    @classmethod
    def validate_headline(cls, v: str) -> str:
        cleaned = _clean_headline_text(v)
        if not cleaned:
            raise ValueError("Headline must not be empty or whitespace only")
        return cleaned


# ────────────────────────────────────────────────────────────────────────────
# Timestamp & Text Normalization Helpers
# ────────────────────────────────────────────────────────────────────────────

def normalize_timestamp(val: Any) -> Optional[str]:
    """Convert arbitrary date representations into an ISO-8601 UTC string.

    Supports:
    - Unix epoch integer/float (seconds)
    - RFC 822 / 2822 strings (standard RSS pubDate format)
    - ISO-8601 formatted strings (with or without 'Z')
    - Standard SQL-like timestamps ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d')

    Returns:
        ISO-8601 UTC timestamp string, or None if conversion fails.
    """
    if val is None or val == "":
        return None

    if isinstance(val, (int, float)):
        try:
            # Unix epoch seconds
            return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
        except Exception:
            return None

    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            return None

        # 1. Try RFC 822 / 2822 (standard RSS date)
        try:
            parsed = email.utils.parsedate_to_datetime(cleaned)
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            pass

        # 2. Try ISO-8601 formats
        try:
            iso_clean = cleaned.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            pass

        # 3. Try standard string formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                continue

    return None


def _clean_headline_text(raw_text: str) -> str:
    """Unescape HTML and collapse whitespace in headline strings."""
    if not raw_text:
        return ""
    unescaped = html.unescape(raw_text)
    return re.sub(r"\s+", " ", unescaped).strip()


def _normalize_for_dedup(text: str) -> str:
    """Generate a normalized alphanumeric token representation for similarity checks."""
    if not text:
        return ""
    # Strip common publisher suffixes like "- Moneycontrol" or "| Reuters"
    text = re.sub(r"[\-|]\s+[A-Za-z0-9\.\s]+$", "", text)
    # Strip non-alphanumeric characters and lowercase
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _clean_url(url: Optional[str]) -> Optional[str]:
    """Clean query tracking parameters from article URLs."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    # Strip tracking params like ?utm_*
    url = re.sub(r"[?&]utm_[^&]+", "", url)
    url = re.sub(r"\?&", "?", url)
    url = url.rstrip("?&")
    return url


# ────────────────────────────────────────────────────────────────────────────
# Provider 1: Tavily API
# ────────────────────────────────────────────────────────────────────────────

def fetch_tavily_news(
    ticker: str,
    max_results: int = 5,
    api_key: Optional[str] = None,
    timeout: float = 8.0,
) -> List[NewsItem]:
    """Fetch company news using the Tavily Search API.

    Args:
        ticker: NSE ticker symbol (e.g. 'TCS.NS').
        max_results: Maximum number of articles to return.
        api_key: Optional Tavily API key override. If None, reads TAVILY_API_KEY from env.
        timeout: Network timeout in seconds.

    Returns:
        List of validated NewsItem models. Returns empty list on failure without raising.
    """
    key = api_key or os.getenv("TAVILY_API_KEY", "").strip()
    if not key or key.startswith("your_") or key == "your_tavily_api_key_here":
        logger.warning("fetch_tavily_news: TAVILY_API_KEY is not configured or is a placeholder.")
        return []

    company_name = NSE_COMPANY_NAMES.get(ticker, ticker.replace(".NS", ""))
    query = f"{company_name} {ticker.replace('.NS', '')} stock financial earnings news"

    payload = {
        "api_key": key,
        "query": query,
        "topic": "news",
        "search_depth": "basic",
        "max_results": max_results,
    }

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        if response.status_code != 200:
            logger.warning(
                "fetch_tavily_news [%s]: API returned status %d: %s",
                ticker,
                response.status_code,
                response.text[:200],
            )
            return []

        data = response.json()
        results = data.get("results", [])
        news_items: List[NewsItem] = []

        for item in results:
            raw_title = item.get("title", "")
            headline = _clean_headline_text(raw_title)
            if not headline:
                continue

            raw_url = item.get("url")
            url = _clean_url(raw_url)
            snippet = _clean_headline_text(item.get("content", "")) or None
            published_at = normalize_timestamp(item.get("published_date"))

            # Tavily does not always have explicit source domain, extract from URL if possible
            source = "Tavily"
            if url:
                domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
                if domain_match:
                    source = domain_match.group(1)

            try:
                news_item = NewsItem(
                    ticker=ticker,
                    headline=headline,
                    source=source,
                    published_at=published_at,
                    url=url,
                    provider="tavily",
                    snippet=snippet,
                )
                news_items.append(news_item)
            except Exception as val_err:
                logger.debug("Tavily validation error for item: %s", val_err)
                continue

        logger.info("fetch_tavily_news [%s]: Retrieved %d items", ticker, len(news_items))
        return news_items

    except requests.Timeout:
        logger.warning("fetch_tavily_news [%s]: Request timed out after %.1fs", ticker, timeout)
        return []
    except Exception as exc:
        logger.warning("fetch_tavily_news [%s]: Request failed: %s", ticker, exc)
        return []


# ────────────────────────────────────────────────────────────────────────────
# Provider 2: Google News RSS
# ────────────────────────────────────────────────────────────────────────────

def fetch_google_rss_news(
    ticker: str,
    max_results: int = 5,
    timeout: float = 8.0,
) -> List[NewsItem]:
    """Fetch company news from the Google News RSS feed for Indian markets.

    Requires zero external SDKs, utilizing standard XML parsing over HTTPS.

    Args:
        ticker: NSE ticker symbol (e.g. 'TCS.NS').
        max_results: Maximum articles to extract.
        timeout: Network timeout in seconds.

    Returns:
        List of validated NewsItem models.
    """
    import xml.etree.ElementTree as ET

    company_name = NSE_COMPANY_NAMES.get(ticker, ticker.replace(".NS", ""))
    clean_sym = ticker.replace(".NS", "")
    query = f'"{company_name}" OR "{clean_sym}" stock earnings'

    # Google News RSS endpoint configured for India English (en-IN)
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            logger.warning("fetch_google_rss_news [%s]: Status %d", ticker, response.status_code)
            return []

        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        news_items: List[NewsItem] = []

        for item in items[: max_results * 2]:  # parse candidate buffer before dedup
            title_elem = item.find("title")
            raw_title = title_elem.text if title_elem is not None and title_elem.text else ""
            if not _clean_headline_text(raw_title):
                continue

            # Determine publisher source and clean headline
            source_elem = item.find("source")
            source = source_elem.text.strip() if (source_elem is not None and source_elem.text) else ""

            # Google News RSS titles end with '- SourceName'
            if " - " in raw_title:
                parts = raw_title.rsplit(" - ", 1)
                headline = _clean_headline_text(parts[0])
                if not source:
                    source = parts[1].strip()
            else:
                headline = _clean_headline_text(raw_title)

            if not headline:
                continue

            if not source:
                source = "Google News"

            link_elem = item.find("link")
            raw_url = link_elem.text if link_elem is not None and link_elem.text else None
            article_url = _clean_url(raw_url)

            pub_date_elem = item.find("pubDate")
            raw_pub_date = pub_date_elem.text if pub_date_elem is not None else None
            published_at = normalize_timestamp(raw_pub_date)

            desc_elem = item.find("description")
            snippet = None
            if desc_elem is not None and desc_elem.text:
                clean_snippet = re.sub(r"<[^>]+>", "", desc_elem.text)
                clean_snippet = _clean_headline_text(clean_snippet)
                snippet = clean_snippet if clean_snippet else None

            try:
                news_item = NewsItem(
                    ticker=ticker,
                    headline=headline,
                    source=source,
                    published_at=published_at,
                    url=article_url,
                    provider="google_news",
                    snippet=snippet,
                )
                news_items.append(news_item)
            except Exception as val_err:
                logger.debug("Google RSS validation error: %s", val_err)
                continue

            if len(news_items) >= max_results:
                break

        logger.info("fetch_google_rss_news [%s]: Retrieved %d items", ticker, len(news_items))
        return news_items

    except requests.Timeout:
        logger.warning("fetch_google_rss_news [%s]: Timeout after %.1fs", ticker, timeout)
        return []
    except Exception as exc:
        logger.warning("fetch_google_rss_news [%s]: Failed: %s", ticker, exc)
        return []


# ────────────────────────────────────────────────────────────────────────────
# Provider 3: Yahoo Finance News
# ────────────────────────────────────────────────────────────────────────────

def fetch_yfinance_news(
    ticker: str,
    max_results: int = 5,
) -> List[NewsItem]:
    """Fetch company news using yfinance ticker news interface.

    Handles yfinance connection errors and structure variances safely.

    Args:
        ticker: NSE ticker symbol (e.g. 'TCS.NS').
        max_results: Maximum articles to extract.

    Returns:
        List of validated NewsItem models.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("fetch_yfinance_news: yfinance package is not installed.")
        return []

    try:
        tk = yf.Ticker(ticker)
        raw_news = getattr(tk, "news", None)
        if not raw_news or not isinstance(raw_news, list):
            # Try plain symbol without .NS suffix if empty
            if ticker.endswith(".NS"):
                base_sym = ticker.replace(".NS", "")
                tk_base = yf.Ticker(base_sym)
                raw_news = getattr(tk_base, "news", None)

        if not raw_news or not isinstance(raw_news, list):
            logger.info("fetch_yfinance_news [%s]: No articles returned by Yahoo Finance", ticker)
            return []

        news_items: List[NewsItem] = []
        for entry in raw_news[:max_results]:
            # Yahoo Finance news items can have two structures (content nested or flat)
            content = entry.get("content", {}) if isinstance(entry.get("content"), dict) else entry

            raw_title = content.get("title") or entry.get("title") or ""
            headline = _clean_headline_text(raw_title)
            if not headline:
                continue

            source = (
                content.get("provider", {}).get("displayName")
                if isinstance(content.get("provider"), dict)
                else (entry.get("publisher") or "Yahoo Finance")
            )

            raw_url = content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else entry.get("link")
            url = _clean_url(raw_url)

            raw_time = content.get("pubDate") or entry.get("providerPublishTime")
            published_at = normalize_timestamp(raw_time)

            snippet = _clean_headline_text(content.get("summary") or entry.get("summary") or "") or None

            try:
                item = NewsItem(
                    ticker=ticker,
                    headline=headline,
                    source=source or "Yahoo Finance",
                    published_at=published_at,
                    url=url,
                    provider="yfinance",
                    snippet=snippet,
                )
                news_items.append(item)
            except Exception as val_err:
                logger.debug("yfinance validation error: %s", val_err)
                continue

        logger.info("fetch_yfinance_news [%s]: Retrieved %d items", ticker, len(news_items))
        return news_items

    except Exception as exc:
        # e.g., curl_cffi proxy connection error, offline status, or rate limits
        logger.warning("fetch_yfinance_news [%s]: Provider error: %s", ticker, exc)
        return []


# ────────────────────────────────────────────────────────────────────────────
# Deduplication and Multi-Source Aggregator
# ────────────────────────────────────────────────────────────────────────────

def deduplicate_news(items: Sequence[NewsItem]) -> List[NewsItem]:
    """Deduplicate headlines across providers using canonical URL and title tokens.

    Preserves the earliest seen item or the item with the richer description.

    Args:
        items: Sequence of NewsItem objects.

    Returns:
        List of unique NewsItem objects.
    """
    seen_urls: Set[str] = set()
    seen_tokens: Set[str] = set()
    deduped: List[NewsItem] = []

    for item in items:
        # 1. URL-based deduplication
        if item.url:
            canonical_url = item.url.lower().rstrip("/")
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)

        # 2. Tokenized headline text deduplication
        token = _normalize_for_dedup(item.headline)
        if token:
            if token in seen_tokens:
                continue
            seen_tokens.add(token)

        deduped.append(item)

    return deduped


def fetch_company_news(
    tickers: Sequence[str] | str,
    max_per_source: int = 5,
    providers: Optional[Sequence[str]] = None,
    use_cache: bool = True,
    cache_ttl_hours: int = 4,
) -> Dict[str, List[NewsItem]]:
    """Collect and merge company news across configured providers.

    Args:
        tickers: Single ticker or sequence of tickers (e.g. ['TCS.NS', 'INFY.NS']).
        max_per_source: Headline limit per provider.
        providers: List of providers to query. Defaults to ['google_news', 'tavily', 'yfinance'].
        use_cache: If True, uses existing non-expired cached data if available.
        cache_ttl_hours: Cache time-to-live in hours before forcing a refresh.

    Returns:
        Dictionary mapping ticker string -> list of unique NewsItem objects.
    """
    if isinstance(tickers, str):
        ticker_list = [tickers]
    else:
        ticker_list = list(tickers)

    if providers is None:
        providers = ["google_news", "tavily", "yfinance"]

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _NEWS_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Check existing master cache
    all_cached_data = _load_cache_data()
    results: Dict[str, List[NewsItem]] = {}
    tickers_to_fetch: List[str] = []

    for ticker in ticker_list:
        if use_cache and ticker in all_cached_data:
            cache_entry = all_cached_data[ticker]
            cached_time_str = cache_entry.get("cached_at")
            cached_items_raw = cache_entry.get("articles", [])

            is_valid = False
            if cached_time_str:
                try:
                    cached_dt = datetime.fromisoformat(cached_time_str)
                    age_hours = (datetime.now(timezone.utc) - cached_dt).total_seconds() / 3600.0
                    if age_hours < cache_ttl_hours and cached_items_raw:
                        is_valid = True
                except Exception:
                    is_valid = False

            if is_valid:
                valid_items: List[NewsItem] = []
                for raw_dict in cached_items_raw:
                    try:
                        valid_items.append(NewsItem(**raw_dict))
                    except Exception:
                        continue
                if valid_items:
                    results[ticker] = valid_items
                    logger.info("Using cached news for %s (%d articles)", ticker, len(valid_items))
                    continue

        tickers_to_fetch.append(ticker)

    # 2. Fetch from providers for remaining tickers
    for ticker in tickers_to_fetch:
        collected: List[NewsItem] = []

        # Provider: Google News RSS
        if "google_news" in providers:
            try:
                gn_items = fetch_google_rss_news(ticker, max_results=max_per_source)
                collected.extend(gn_items)
            except Exception as exc:
                logger.warning("fetch_company_news: google_news failed for %s: %s", ticker, exc)
            time.sleep(0.1)  # respectful delay

        # Provider: Tavily API
        if "tavily" in providers:
            try:
                tv_items = fetch_tavily_news(ticker, max_results=max_per_source)
                collected.extend(tv_items)
            except Exception as exc:
                logger.warning("fetch_company_news: tavily failed for %s: %s", ticker, exc)
            time.sleep(0.1)

        # Provider: Yahoo Finance
        if "yfinance" in providers:
            try:
                yf_items = fetch_yfinance_news(ticker, max_results=max_per_source)
                collected.extend(yf_items)
            except Exception as exc:
                logger.warning("fetch_company_news: yfinance failed for %s: %s", ticker, exc)

        # Deduplicate
        unique_items = deduplicate_news(collected)
        results[ticker] = unique_items

        # Update cache dictionary
        all_cached_data[ticker] = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "articles": [item.model_dump() for item in unique_items],
        }

    # 3. Persist to cache file and dated snapshot
    _save_cache_data(all_cached_data)

    return results


# ────────────────────────────────────────────────────────────────────────────
# Cache Storage & Retrieval
# ────────────────────────────────────────────────────────────────────────────

def _load_cache_data() -> Dict[str, Any]:
    """Load the raw master cache JSON dictionary."""
    if not _HEADLINES_CACHE_FILE.exists():
        return {}
    try:
        with open(_HEADLINES_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tickers", {}) if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not read headlines cache file: %s", exc)
        return {}


def _save_cache_data(tickers_data: Dict[str, Any]) -> None:
    """Save ticker articles to master cache and daily dated snapshot."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _NEWS_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        now_utc = datetime.now(timezone.utc)
        payload = {
            "updated_at": now_utc.isoformat(),
            "total_tickers": len(tickers_data),
            "tickers": tickers_data,
        }

        # Write master cache
        with open(_HEADLINES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        # Write dated snapshot: headlines_YYYY-MM-DD.json
        date_str = now_utc.strftime("%Y-%m-%d")
        snapshot_file = _NEWS_SNAPSHOTS_DIR / f"headlines_{date_str}.json"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        logger.info("Persisted headlines cache to %s and %s", _HEADLINES_CACHE_FILE, snapshot_file)
    except Exception as exc:
        logger.warning("Failed to persist headlines cache: %s", exc)


# ────────────────────────────────────────────────────────────────────────────
# Screener Integration Helper (Contract API)
# ────────────────────────────────────────────────────────────────────────────

def get_latest_news_for_ticker(
    ticker: str,
    limit: int = 5,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Retrieve structured news articles for a single stock ticker.

    Designed as the primary entry point for Kartik's Screener Agent and UI components.

    Args:
        ticker: NSE ticker symbol (e.g. 'TCS.NS' or 'INFY.NS').
        limit: Maximum number of articles to return.
        use_cache: Whether to read from local cache first.

    Returns:
        List of article dictionaries conforming to the NewsItem schema:
        [
            {
                "ticker": "TCS.NS",
                "headline": "...",
                "source": "Moneycontrol",
                "published_at": "2026-10-30T09:15:00+00:00",
                "url": "https://...",
                "provider": "google_news",
                "snippet": "..."
            },
            ...
        ]
    """
    clean_ticker = ticker.strip().upper()
    if not clean_ticker.endswith(".NS") and "." not in clean_ticker:
        clean_ticker = f"{clean_ticker}.NS"

    news_by_ticker = fetch_company_news(
        tickers=[clean_ticker],
        max_per_source=limit,
        use_cache=use_cache,
    )

    items = news_by_ticker.get(clean_ticker, [])
    # Return as list of serializable dictionaries
    return [item.model_dump() for item in items[:limit]]
