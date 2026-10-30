"""
Fetch headlines for candidate tickers from multiple sources
Saves to JSON file for Kartik's Screener to read
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import yfinance as yf

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

try:
    import gnews
except ImportError:
    gnews = None


def fetch_headlines_tavily(ticker: str, max_results: int = 10) -> List[Dict]:
    """Fetch headlines using Tavily API"""
    if not TavilyClient:
        print("⚠️  Tavily not installed. Install with: pip install tavily-python")
        return []
    
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(query=f"{ticker} stock news", max_results=max_results)
        
        headlines = []
        for result in response.get("results", []):
            headlines.append({
                "source": "Tavily",
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "published_date": result.get("published_date", "")
            })
        return headlines
    except Exception as e:
        print(f"❌ Tavily fetch error for {ticker}: {e}")
        return []


def fetch_headlines_gnews(ticker: str, max_results: int = 10) -> List[Dict]:
    """Fetch headlines using GNews API"""
    if not gnews:
        print("⚠️  GNews not installed. Install with: pip install gnews")
        return []
    
    try:
        from gnews import GNews
        news_client = GNews()
        headlines_data = news_client.get_news(ticker)
        
        headlines = []
        for article in headlines_data[:max_results]:
            headlines.append({
                "source": "GNews",
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "snippet": article.get("description", ""),
                "published_date": article.get("published date", "")
            })
        return headlines
    except Exception as e:
        print(f"❌ GNews fetch error for {ticker}: {e}")
        return []


def fetch_headlines_yfinance(ticker: str, max_results: int = 10) -> List[Dict]:
    """Fetch headlines using yfinance news"""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news[:max_results] if stock.news else []
        
        headlines = []
        for article in news:
            headlines.append({
                "source": "yFinance",
                "title": article.get("title", ""),
                "url": article.get("link", ""),
                "snippet": article.get("summary", ""),
                "published_date": article.get("providerPublishTime", "")
            })
        return headlines
    except Exception as e:
        print(f"❌ yFinance fetch error for {ticker}: {e}")
        return []


def fetch_all_headlines(tickers: List[str], max_results: int = 10, 
                       sources: Optional[List[str]] = None) -> Dict:
    """
    Fetch headlines from all available sources for given tickers
    
    Args:
        tickers: List of stock tickers
        max_results: Max headlines per source per ticker
        sources: List of sources to use ['tavily', 'gnews', 'yfinance']
                If None, tries all available
    
    Returns:
        Dict with ticker -> headlines mapping
    """
    if sources is None:
        sources = ['yfinance', 'gnews', 'tavily']  # Try in order of reliability
    
    all_headlines = {}
    
    for ticker in tickers:
        print(f"\n🔍 Fetching headlines for {ticker}...")
        ticker_headlines = []
        
        if 'yfinance' in sources:
            print(f"  → yFinance...", end=" ")
            yf_headlines = fetch_headlines_yfinance(ticker, max_results)
            ticker_headlines.extend(yf_headlines)
            print(f"✓ ({len(yf_headlines)} results)")
        
        if 'gnews' in sources:
            print(f"  → GNews...", end=" ")
            gn_headlines = fetch_headlines_gnews(ticker, max_results)
            ticker_headlines.extend(gn_headlines)
            print(f"✓ ({len(gn_headlines)} results)")
        
        if 'tavily' in sources:
            print(f"  → Tavily...", end=" ")
            tv_headlines = fetch_headlines_tavily(ticker, max_results)
            ticker_headlines.extend(tv_headlines)
            print(f"✓ ({len(tv_headlines)} results)")
        
        all_headlines[ticker] = ticker_headlines
        print(f"  📰 Total: {len(ticker_headlines)} headlines")
    
    return all_headlines


def save_headlines(headlines: Dict, output_file: str = "data/headlines.json"):
    """Save headlines to JSON file"""
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "headlines": headlines
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Headlines saved to {output_file}")
    return output_file


def main():
    """Main entry point"""
    import sys
    
    # Get tickers from command line or use defaults
    if len(sys.argv) > 1:
        tickers = sys.argv[1].split(',')
    else:
        # Default candidate tickers
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN']
    
    print("=" * 60)
    print("📰 HEADLINE FETCHER FOR SCREENER")
    print("=" * 60)
    print(f"Fetching headlines for: {', '.join(tickers)}")
    
    # Fetch all headlines
    headlines = fetch_all_headlines(tickers, max_results=5)
    
    # Save to file
    output_file = save_headlines(headlines)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for ticker, articles in headlines.items():
        print(f"{ticker}: {len(articles)} headlines")
        for i, article in enumerate(articles[:2], 1):
            print(f"  {i}. {article['title'][:60]}...")
    
    return output_file


if __name__ == "__main__":
    main()
