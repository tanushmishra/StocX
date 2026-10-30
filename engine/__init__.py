"""Market-Neutral Hedge Builder — Quantitative Finance Engine.

This package provides a deterministic, production-grade quantitative finance
engine for constructing, backtesting, and verifying market-neutral long–short
equity pairs on NSE-listed stocks.

Modules
-------
data_fetcher
    Price fetching, sector constituents, fundamentals, and F&O lot sizes.
beta_calculator
    Static OLS, EWMA, and rolling-window beta estimation.
cointegration
    Engle-Granger test, spread Z-score, Ornstein-Uhlenbeck half-life.
portfolio
    Beta-neutral weight solver, F&O lot conversion, correlation matrix.
backtester
    Pair backtesting, risk metrics, and stress-test regimes.
verifier
    Adversarial guardrails and fundamental scoring.
hedge_pipeline
    End-to-end pipeline orchestrator.
"""

from engine.backtester import backtest_pair, calc_metrics, stress_test
from engine.beta_calculator import (
    compute_ewma_beta,
    compute_rolling_beta,
    compute_static_beta,
)
from engine.cointegration import (
    compute_spread_zscore,
    engle_granger_test,
    ou_half_life,
)
from engine.data_fetcher import (
    audit_cache_directory,
    fetch_prices,
    get_data_source,
    get_fno_lot_sizes,
    get_fundamentals,
    get_sector_constituents,
    validate_cached_dataframe,
)
from engine.hedge_pipeline import run_full_hedge_analysis
from engine.news_fetcher import (
    fetch_ticker_news,
    format_news_for_screener,
)
from engine.portfolio import (
    compute_beta_neutral_weights,
    compute_correlation_matrix,
    convert_to_fno_lots,
)
from engine.verifier import score_candidate, verify_pair

__all__ = [
    # data_fetcher
    "fetch_prices",
    "get_data_source",
    "validate_cached_dataframe",
    "audit_cache_directory",
    "get_sector_constituents",
    "get_fundamentals",
    "get_fno_lot_sizes",
    # news_fetcher
    "fetch_ticker_news",
    "format_news_for_screener",
    # beta_calculator
    "compute_static_beta",
    "compute_ewma_beta",
    "compute_rolling_beta",
    # cointegration
    "engle_granger_test",
    "compute_spread_zscore",
    "ou_half_life",
    # portfolio
    "compute_beta_neutral_weights",
    "convert_to_fno_lots",
    "compute_correlation_matrix",
    # backtester
    "backtest_pair",
    "calc_metrics",
    "stress_test",
    # verifier
    "verify_pair",
    "score_candidate",
    # hedge_pipeline
    "run_full_hedge_analysis",
]
