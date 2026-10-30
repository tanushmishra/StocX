"""Unit tests for the Financial News Intelligence Engine (engine.news_collector).

Verifies multi-provider news fetching, schema validation, zero-hallucination invariants,
timestamp normalization, deduplication, fault tolerance, and cache persistence.
All tests are completely hermetic and never hit live network endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from engine.news_collector import (
    NewsItem,
    deduplicate_news,
    fetch_company_news,
    fetch_google_rss_news,
    fetch_tavily_news,
    fetch_yfinance_news,
    get_latest_news_for_ticker,
    normalize_timestamp,
)


# ────────────────────────────────────────────────────────────────────────────
# Test Fixtures & Sample Payloads
# ────────────────────────────────────────────────────────────────────────────

SAMPLE_TAVILY_PAYLOAD = {
    "results": [
        {
            "title": "TCS Wins Multi-Million Dollar BFSI Cloud Transformation Deal",
            "url": "https://www.reuters.com/technology/tcs-cloud-deal-2026?utm_source=rss",
            "content": "Tata Consultancy Services announced a major multi-year digital transformation deal.",
            "published_date": "2026-10-30T09:15:00Z",
        }
    ]
}

SAMPLE_GOOGLE_RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News - Search</title>
    <item>
      <title>Infosys raises FY27 full-year revenue guidance - The Economic Times</title>
      <link>https://economictimes.indiatimes.com/tech/infy-guidance-1234.html?utm_campaign=feed</link>
      <pubDate>Fri, 30 Oct 2026 08:30:00 GMT</pubDate>
      <source url="https://economictimes.indiatimes.com">The Economic Times</source>
      <description>&lt;p&gt;Infosys management revised upward its constant-currency growth target.&lt;/p&gt;</description>
    </item>
  </channel>
</rss>
"""


# ────────────────────────────────────────────────────────────────────────────
# 1. Valid Tavily Response
# ────────────────────────────────────────────────────────────────────────────

def test_valid_tavily_response():
    """Verify successful parsing of Tavily API search response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_TAVILY_PAYLOAD

    with patch("requests.post", return_value=mock_resp):
        items = fetch_tavily_news("TCS.NS", max_results=5, api_key="test_valid_key")

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, NewsItem)
    assert item.ticker == "TCS.NS"
    assert "TCS Wins Multi-Million Dollar" in item.headline
    assert item.provider == "tavily"
    assert item.source == "reuters.com"
    assert item.published_at == "2026-10-30T09:15:00+00:00"
    assert "utm_source" not in (item.url or "")
    assert "transformation deal" in (item.snippet or "")


# ────────────────────────────────────────────────────────────────────────────
# 2. Valid Google RSS Response
# ────────────────────────────────────────────────────────────────────────────

def test_valid_google_rss_response():
    """Verify successful parsing of Google News RSS XML."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = SAMPLE_GOOGLE_RSS_XML

    with patch("requests.get", return_value=mock_resp):
        items = fetch_google_rss_news("INFY.NS", max_results=5)

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, NewsItem)
    assert item.ticker == "INFY.NS"
    assert item.headline == "Infosys raises FY27 full-year revenue guidance"
    assert item.source == "The Economic Times"
    assert item.provider == "google_news"
    assert item.published_at == "2026-10-30T08:30:00+00:00"
    assert "constant-currency growth" in (item.snippet or "")
    assert "utm_campaign" not in (item.url or "")


# ────────────────────────────────────────────────────────────────────────────
# 3. Valid Yahoo Finance Response
# ────────────────────────────────────────────────────────────────────────────

def test_valid_yfinance_response():
    """Verify successful parsing of yfinance news items."""
    mock_news_data = [
        {
            "title": "Wipro completes strategic acquisition of AI consulting firm",
            "publisher": "Reuters",
            "link": "https://www.reuters.com/business/wipro-ai-deal",
            "providerPublishTime": 1730280000,
            "summary": "Wipro announced closing the purchase today.",
        }
    ]

    mock_ticker_instance = MagicMock()
    mock_ticker_instance.news = mock_news_data

    with patch("yfinance.Ticker", return_value=mock_ticker_instance):
        items = fetch_yfinance_news("WIPRO.NS", max_results=5)

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, NewsItem)
    assert item.ticker == "WIPRO.NS"
    assert "Wipro completes strategic acquisition" in item.headline
    assert item.source == "Reuters"
    assert item.provider == "yfinance"
    assert item.published_at is not None
    assert item.url == "https://www.reuters.com/business/wipro-ai-deal"
    assert "closing the purchase" in (item.snippet or "")


# ────────────────────────────────────────────────────────────────────────────
# 4. Empty Provider Response
# ────────────────────────────────────────────────────────────────────────────

def test_empty_provider_response():
    """Verify all providers return empty list without crashing when no articles exist."""
    # Tavily empty
    mock_tavily = MagicMock()
    mock_tavily.status_code = 200
    mock_tavily.json.return_value = {"results": []}

    with patch("requests.post", return_value=mock_tavily):
        assert fetch_tavily_news("TCS.NS", api_key="valid_key") == []

    # Google RSS empty
    mock_rss = MagicMock()
    mock_rss.status_code = 200
    mock_rss.content = b"<?xml version='1.0'?><rss version='2.0'><channel></channel></rss>"

    with patch("requests.get", return_value=mock_rss):
        assert fetch_google_rss_news("TCS.NS") == []

    # yfinance empty
    mock_yf = MagicMock()
    mock_yf.news = []
    with patch("yfinance.Ticker", return_value=mock_yf):
        assert fetch_yfinance_news("TCS.NS") == []


# ────────────────────────────────────────────────────────────────────────────
# 5. Missing API Key
# ────────────────────────────────────────────────────────────────────────────

def test_missing_api_key():
    """Verify Tavily gracefully returns empty list without network calls when key is missing."""
    with patch.dict("os.environ", {"TAVILY_API_KEY": ""}, clear=True):
        with patch("requests.post") as mock_post:
            items = fetch_tavily_news("TCS.NS", api_key=None)
            assert items == []
            mock_post.assert_not_called()

    # Also test placeholder key
    with patch.dict("os.environ", {"TAVILY_API_KEY": "your_tavily_api_key_here"}):
        with patch("requests.post") as mock_post:
            items = fetch_tavily_news("TCS.NS", api_key=None)
            assert items == []
            mock_post.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────
# 6. Provider Timeout
# ────────────────────────────────────────────────────────────────────────────

def test_provider_timeout():
    """Verify that network timeouts are caught cleanly and return empty lists."""
    with patch("requests.post", side_effect=requests.Timeout("Request timed out")):
        items = fetch_tavily_news("TCS.NS", api_key="valid_key")
        assert items == []

    with patch("requests.get", side_effect=requests.Timeout("RSS timed out")):
        items = fetch_google_rss_news("TCS.NS")
        assert items == []


# ────────────────────────────────────────────────────────────────────────────
# 7. Duplicate Headline Detection
# ────────────────────────────────────────────────────────────────────────────

def test_duplicate_headline_detection():
    """Verify that identical headlines across providers or tracking URLs are deduplicated."""
    item1 = NewsItem(
        ticker="TCS.NS",
        headline="TCS Reports Strong Q3 Net Profit Growth - Moneycontrol",
        source="Moneycontrol",
        published_at="2026-10-30T09:00:00+00:00",
        url="https://www.moneycontrol.com/news/tcs-q3",
        provider="google_news",
        snippet="TCS Q3 profit grew 6% YoY.",
    )
    # Exact same normalized headline with minor suffix variance and tracking query
    item2 = NewsItem(
        ticker="TCS.NS",
        headline="TCS Reports Strong Q3 Net Profit Growth - Reuters",
        source="Reuters",
        published_at="2026-10-30T09:05:00+00:00",
        url="https://www.reuters.com/news/tcs-q3",
        provider="tavily",
        snippet="Different snippet for same corporate event.",
    )
    # Distinct headline
    item3 = NewsItem(
        ticker="TCS.NS",
        headline="HCL Tech announces partnership with AWS",
        source="Mint",
        published_at="2026-10-30T10:00:00+00:00",
        url="https://www.livemint.com/news/hcl-aws",
        provider="google_news",
        snippet="Cloud partnership.",
    )

    deduped = deduplicate_news([item1, item2, item3])
    assert len(deduped) == 2
    assert deduped[0].headline == item1.headline
    assert deduped[1].headline == item3.headline


# ────────────────────────────────────────────────────────────────────────────
# 8. Invalid Headline Data
# ────────────────────────────────────────────────────────────────────────────

def test_invalid_headline_data():
    """Verify items with blank headlines or invalid structure are safely filtered."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>   </title>
          <link>https://example.com/empty</link>
        </item>
        <item>
          <title>Valid Headline Here</title>
          <link>https://example.com/valid</link>
        </item>
      </channel>
    </rss>
    """

    with patch("requests.get", return_value=mock_resp):
        items = fetch_google_rss_news("TCS.NS")

    assert len(items) == 1
    assert items[0].headline == "Valid Headline Here"


# ────────────────────────────────────────────────────────────────────────────
# 9. Missing Publication Date
# ────────────────────────────────────────────────────────────────────────────

def test_missing_publication_date():
    """Verify missing or unparseable timestamps evaluate strictly to None (no hallucination)."""
    assert normalize_timestamp(None) is None
    assert normalize_timestamp("") is None
    assert normalize_timestamp("invalid-date-string-that-cannot-parse") is None

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "HCL Tech Q3 Review",
                "url": "https://example.com/hcl",
                "published_date": "",  # missing date
            }
        ]
    }

    with patch("requests.post", return_value=mock_resp):
        items = fetch_tavily_news("HCLTECH.NS", api_key="valid_key")

    assert len(items) == 1
    assert items[0].published_at is None


# ────────────────────────────────────────────────────────────────────────────
# 10. Missing Article URL
# ────────────────────────────────────────────────────────────────────────────

def test_missing_article_url():
    """Verify that items without URLs preserve url=None without crashing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Tech Mahindra wins automotive telemetry contract</title>
        </item>
      </channel>
    </rss>
    """

    with patch("requests.get", return_value=mock_resp):
        items = fetch_google_rss_news("TECHM.NS")

    assert len(items) == 1
    assert items[0].url is None
    assert items[0].headline == "Tech Mahindra wins automotive telemetry contract"


# ────────────────────────────────────────────────────────────────────────────
# 11. Cache Save and Reload
# ────────────────────────────────────────────────────────────────────────────

def test_cache_save_and_reload(tmp_path: Path):
    """Verify that fetched news writes to disk cache and is reloaded without network calls."""
    cache_file = tmp_path / "headlines.json"
    snapshot_dir = tmp_path / "news"

    mock_items = [
        NewsItem(
            ticker="LTIM.NS",
            headline="LTIMindtree launches enterprise AI platform",
            source="Financial Express",
            published_at="2026-10-30T10:00:00+00:00",
            url="https://www.financialexpress.com/ltim-ai",
            provider="google_news",
            snippet="Enterprise generative AI platform.",
        )
    ]

    with patch("engine.news_collector._CACHE_DIR", tmp_path), \
         patch("engine.news_collector._HEADLINES_CACHE_FILE", cache_file), \
         patch("engine.news_collector._NEWS_SNAPSHOTS_DIR", snapshot_dir), \
         patch("engine.news_collector.fetch_google_rss_news", return_value=mock_items), \
         patch("engine.news_collector.fetch_tavily_news", return_value=[]), \
         patch("engine.news_collector.fetch_yfinance_news", return_value=[]):

        # First fetch: writes to cache
        results = fetch_company_news(["LTIM.NS"], use_cache=True)
        assert "LTIM.NS" in results
        assert len(results["LTIM.NS"]) == 1
        assert cache_file.exists()

        # Verify disk JSON contents
        with open(cache_file, "r", encoding="utf-8") as f:
            saved_json = json.load(f)
        assert "LTIM.NS" in saved_json["tickers"]
        assert saved_json["tickers"]["LTIM.NS"]["articles"][0]["headline"] == "LTIMindtree launches enterprise AI platform"

        # Second fetch: read through get_latest_news_for_ticker helper
        with patch("engine.news_collector.fetch_google_rss_news") as mock_rss_call:
            latest = get_latest_news_for_ticker("LTIM.NS", limit=5, use_cache=True)
            assert len(latest) == 1
            assert latest[0]["headline"] == "LTIMindtree launches enterprise AI platform"
            # Should have hit cache, not provider
            mock_rss_call.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────
# 12. Fault Tolerance: One Provider Fails While Another Succeeds
# ────────────────────────────────────────────────────────────────────────────

def test_one_provider_failing_while_another_succeeds(tmp_path: Path):
    """Verify that a fatal error in Tavily does not abort Google News processing."""
    cache_file = tmp_path / "headlines.json"
    snapshot_dir = tmp_path / "news"

    mock_google_items = [
        NewsItem(
            ticker="TCS.NS",
            headline="TCS completes core banking modernization",
            source="Business Standard",
            published_at="2026-10-30T11:00:00+00:00",
            url="https://www.business-standard.com/tcs-banking",
            provider="google_news",
            snippet="Core banking system upgraded successfully.",
        )
    ]

    with patch("engine.news_collector._CACHE_DIR", tmp_path), \
         patch("engine.news_collector._HEADLINES_CACHE_FILE", cache_file), \
         patch("engine.news_collector._NEWS_SNAPSHOTS_DIR", snapshot_dir), \
         patch("engine.news_collector.fetch_tavily_news", side_effect=RuntimeError("Tavily 500 Server Error")), \
         patch("engine.news_collector.fetch_yfinance_news", side_effect=ConnectionError("Yahoo offline")), \
         patch("engine.news_collector.fetch_google_rss_news", return_value=mock_google_items):

        # Should NOT raise an exception
        results = fetch_company_news(["TCS.NS"], use_cache=False)

        assert "TCS.NS" in results
        assert len(results["TCS.NS"]) == 1
        assert results["TCS.NS"][0].headline == "TCS completes core banking modernization"
        assert results["TCS.NS"][0].provider == "google_news"
