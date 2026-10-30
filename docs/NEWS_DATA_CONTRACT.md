# Financial News Intelligence Data Contract

**Author:** Dhairya (Financial News Intelligence & Dashboard Layer)  
**Consumer:** Kartik (Fundamental & Catalyst Screener Agent — `agents/screener.py`) & Streamlit UI Layer  
**Engine Module:** [`engine/news_collector.py`](file:///c:/Users/asus/StocX/engine/news_collector.py)  
**Status:** Production Ready (Phase B)

---

## 1. Overview & Architectural Principle

The News Intelligence Engine fetches, validates, deduplicates, and caches verified corporate and financial headlines for Indian NSE equities (e.g. `TCS.NS`, `INFY.NS`, `WIPRO.NS`, `HCLTECH.NS`, `TECHM.NS`, `LTIM.NS`).

### The Zero-Hallucination Invariant
- **No invented headlines:** Every headline originates verbatim from an authenticated provider or verified RSS publisher.
- **No synthetic timestamps or URLs:** When published dates or article URLs are unavailable, they remain `null` (`None` in Python).
- **No fabricated sentiment scores:** Qualitative narrative synthesis is handled by LLM reasoning (Gemini Flash) in Kartik's Screener node; numbers and facts are never generated out of thin air.
- **Resilient Multi-Provider Fallback:** The engine queries **Google News RSS**, **Tavily**, and **Yahoo Finance**. If any provider fails (e.g. invalid API key, network timeout, connection block), other providers fulfill the request and the pipeline never crashes.

---

## 2. File Locations & Persistence

| Resource | Path | Description |
| :--- | :--- | :--- |
| **Python Module** | `engine/news_collector.py` | Core engine, Pydantic schema, providers, deduplication, and helper APIs. |
| **Active Master Cache** | `data_cache/headlines.json` | Master JSON cache containing the latest retrieved headlines for all screened tickers. |
| **Daily Snapshots** | `data_cache/news/headlines_YYYY-MM-DD.json` | Dated snapshots for historical verification and offline testing. |

---

## 3. Schema & Field Definitions

Each news item strictly conforms to the `NewsItem` Pydantic model:

```json
{
  "ticker": "TCS.NS",
  "headline": "TCS Q3 profit up 5% as BFSI demand stabilizes",
  "source": "Moneycontrol",
  "published_at": "2026-10-30T09:15:00+00:00",
  "url": "https://www.moneycontrol.com/news/business/earnings/tcs-q3-results-1234.html",
  "provider": "google_news",
  "snippet": "Tata Consultancy Services reported a 5.0% rise in net profit for the third quarter..."
}
```

### Detailed Field Specification

| Field Name | Type | Nullable | Description & Invariants |
| :--- | :--- | :--- | :--- |
| `ticker` | `string` | **No** | Full Yahoo Finance / NSE symbol with suffix (e.g., `"TCS.NS"`, `"INFY.NS"`). |
| `headline` | `string` | **No** | Verbatim article headline with HTML unescaped and redundant whitespace collapsed. |
| `source` | `string` | **No** | Verified publishing outlet (e.g., `"The Economic Times"`, `"Moneycontrol"`, `"Reuters"`). |
| `published_at` | `string` | **Yes** | Standard **ISO-8601 UTC timestamp** (e.g., `"2026-10-30T09:15:00+00:00"`). If unparseable or absent, returns `null`. |
| `url` | `string` | **Yes** | Direct canonical article link. Query tracking tokens (e.g. `utm_*`) are stripped. If absent, returns `null`. |
| `provider` | `string` | **No** | Engine provider tag: strictly one of `"google_news"`, `"tavily"`, or `"yfinance"`. |
| `snippet` | `string` | **Yes** | Clean text excerpt or summary. HTML tags are stripped. If absent, returns `null`. |

---

## 4. How Kartik's Screener Agent Consumes the News

Kartik can consume the news in `agents/screener.py` via two alternative methods:

### Method A: Direct Python Helper (Recommended)

Call `get_latest_news_for_ticker()` inside `screener_node`:

```python
from engine.news_collector import get_latest_news_for_ticker

# Inside screener_node(state: HedgeBuilderState):
for ticker in sector_tickers:
    # Fetch top 3 latest verified news items for this candidate
    news_items = get_latest_news_for_ticker(ticker, limit=3, use_cache=True)
    
    # Example format:
    # news_items is a list of dicts conforming to the NewsItem schema
    headlines_summary = "; ".join([item["headline"] for item in news_items])
```

### Method B: Read Directly from the Cache File

If Kartik prefers reading from the cache file without invoking network code:

```python
import json
from pathlib import Path

cache_file = Path("data_cache/headlines.json")
if cache_file.exists():
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)
    
    tcs_news = cache_data.get("tickers", {}).get("TCS.NS", {}).get("articles", [])
```

### Example Prompt Integration for `FundScreenerGPT`

In `agents/screener.py`, Kartik can append the news headlines to the candidate table or prompt:

```text
## Recent Verified Catalysts & News
- TCS.NS: "TCS expands cloud deal with major European bank" (Source: Reuters | Oct 30)
- INFY.NS: "Infosys raises full-year constant currency guidance" (Source: Economic Times | Oct 29)
- WIPRO.NS: "Wipro reports muted Q3 margin expansion amid client delays" (Source: LiveMint | Oct 28)
```

This allows Gemini 2.5 Flash to incorporate real fundamental catalysts without hallucinating corporate events.

---

## 5. Deduplication and URL Normalization Rules

1. **URL Deduplication:** Canonical URLs are lowercased and stripped of trailing slashes and tracking query parameters (`utm_source`, `utm_medium`, `utm_campaign`).
2. **Text Deduplication:** Trailing publisher suffixes (e.g., `" - Economic Times"`, `" | Reuters"`) and non-alphanumeric punctuation are removed for deduplication comparison. If two articles share the same normalized token stream, only the primary unique article is retained.
