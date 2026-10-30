"""Unit tests for engine/news_fetcher.py."""

from unittest.mock import MagicMock, patch
import pytest

from engine.news_fetcher import (
    fetch_tavily_news,
    fetch_ticker_news,
    fetch_yfinance_news,
    format_news_for_screener,
    is_valid_tavily_key,
)


class TestNewsFetcher:
    """Tests for news provider validation, fetching, and fallback behavior."""

    def test_is_valid_tavily_key(self):
        assert is_valid_tavily_key(None) is False
        assert is_valid_tavily_key("") is False
        assert is_valid_tavily_key("short") is False
        assert is_valid_tavily_key("your_tavily_api_key_here") is False
        assert is_valid_tavily_key("dummy") is False
        assert is_valid_tavily_key("tvly-ValidKey123456789") is True

    def test_fetch_tavily_news_skips_when_placeholder_key(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "your_tavily_api_key_here")
        items = fetch_tavily_news("INFY.NS")
        assert items == []

    def test_fetch_tavily_news_success(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-valid-key-12345678")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Infosys raises revenue growth guidance",
                    "domain": "economictimes.indiatimes.com",
                    "url": "https://example.com/news1",
                    "published_date": "2024-01-15",
                    "content": "Infosys reported solid Q3 earnings with positive margin expansion.",
                }
            ]
        }

        with patch("requests.post", return_value=mock_resp):
            items = fetch_tavily_news("INFY.NS")
            assert len(items) == 1
            assert items[0]["title"] == "Infosys raises revenue growth guidance"
            assert items[0]["publisher"] == "economictimes.indiatimes.com"
            assert items[0]["source"] == "tavily"

    def test_fetch_yfinance_news_success(self):
        with patch("engine.news_fetcher.yf") as mock_yf:
            mock_ticker = MagicMock()
            mock_ticker.news = [
                {
                    "title": "TCS signs major multi-year digital transformation deal",
                    "publisher": "Reuters",
                    "link": "https://reuters.com/tcs-deal",
                    "providerPublishTime": 1705312800,
                }
            ]
            mock_yf.Ticker.return_value = mock_ticker

            items = fetch_yfinance_news("TCS.NS")
            assert len(items) == 1
            assert items[0]["title"] == "TCS signs major multi-year digital transformation deal"
            assert items[0]["publisher"] == "Reuters"
            assert items[0]["source"] == "yfinance"

    def test_fetch_ticker_news_prefers_tavily_over_yfinance(self, monkeypatch):
        tavily_items = [{"title": "Tavily headline", "publisher": "Livemint", "source": "tavily"}]
        with patch("engine.news_fetcher.fetch_tavily_news", return_value=tavily_items), patch(
            "engine.news_fetcher.fetch_yfinance_news"
        ) as mock_yf_news:
            res = fetch_ticker_news("INFY.NS")
            assert res == tavily_items
            mock_yf_news.assert_not_called()

    def test_fetch_ticker_news_falls_back_to_yfinance(self):
        yf_items = [{"title": "YFinance headline", "publisher": "Yahoo", "source": "yfinance"}]
        with patch("engine.news_fetcher.fetch_tavily_news", return_value=[]), patch(
            "engine.news_fetcher.fetch_yfinance_news", return_value=yf_items
        ):
            res = fetch_ticker_news("INFY.NS")
            assert res == yf_items

    def test_fetch_ticker_news_returns_empty_when_all_fail(self):
        with patch("engine.news_fetcher.fetch_tavily_news", return_value=[]), patch(
            "engine.news_fetcher.fetch_yfinance_news", return_value=[]
        ):
            res = fetch_ticker_news("INFY.NS")
            assert res == []

    def test_format_news_for_screener(self):
        news_map = {
            "INFY.NS": [
                {"title": "Infosys beats Q3 guidance", "publisher": "Mint", "date": "2024-01-12"}
            ],
            "WIPRO.NS": [],
        }
        formatted = format_news_for_screener(news_map)
        assert "INFY.NS" in formatted
        assert "Infosys beats Q3 guidance" in formatted
        assert "(Mint, 2024-01-12)" in formatted

    def test_format_news_for_screener_empty(self):
        assert "No recent news" in format_news_for_screener({})
        assert "No live news" in format_news_for_screener({"INFY.NS": []})
