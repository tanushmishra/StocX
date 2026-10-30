# 📚 Python API Reference

Complete technical specification for all functions, classes, and types in the **Market-Neutral Hedge Builder**.

---

## 1. Quantitative Engine (`engine/`)

### `engine.data_fetcher`

#### `fetch_prices(tickers: list[str], start: str | None = None, end: str | None = None, lookback_days: int | None = None) -> pd.DataFrame`
Fetches adjusted close prices for specified tickers.
* **Parameters:**
  * `tickers`: List of Yahoo Finance ticker symbols (e.g. `["TCS.NS", "INFY.NS", "^NSEI"]`).
  * `start`: Start date string (`"YYYY-MM-DD"`).
  * `end`: End date string (`"YYYY-MM-DD"`).
  * `lookback_days`: Trailing calendar days if `start`/`end` are omitted.
* **Returns:** `pd.DataFrame` with `DatetimeIndex` and one column per ticker.
* **Behavior:** Checks local disk cache (`data_cache/`). On cache miss, downloads via `yfinance` and caches to disk. On offline/network failure, returns synthetic series.

#### `get_sector_constituents(sector: str) -> list[str]`
Returns constituent tickers for a NIFTY sectoral index.
* **Parameters:** `sector` (e.g. `"NIFTY IT"`, `"NIFTY BANK"`, `"NIFTY AUTO"`, `"NIFTY PHARMA"`).
* **Returns:** List of strings with `.NS` suffix.

#### `get_fundamentals(ticker: str) -> dict`
Retrieves fundamental financial ratios for a given ticker.
* **Returns:** `{"pe_ratio": float, "roe": float, "revenue_growth": float, "debt_to_equity": float}`.

#### `get_fno_lot_sizes() -> dict[str, int]`
Returns exchange-mandated NSE F&O lot sizes for major liquid tickers.

---

### `engine.beta_calculator`

#### `compute_static_beta(stock_returns: pd.Series, market_returns: pd.Series) -> float`
Calculates standard CAPM beta via sample covariance / variance:
$$\beta = \frac{\text{Cov}(R_{\text{stock}}, R_{\text{market}})}{\text{Var}(R_{\text{market}})}$$

#### `compute_ewma_beta(stock_returns: pd.Series, market_returns: pd.Series, span: int = 60, decay: float = 0.94) -> pd.Series`
Calculates exponentially weighted moving average (EWMA) beta using the RiskMetrics recursion:
$$\beta_t = \frac{\text{EWMA Cov}(R_S, R_M, \lambda)}{\text{EWMA Var}(R_M, \lambda)}$$

#### `compute_rolling_beta(stock_returns: pd.Series, market_returns: pd.Series, window: int = 60) -> pd.Series`
Calculates rolling OLS beta over a trailing window of $N$ trading days.

---

### `engine.cointegration`

#### `engle_granger_test(series_a: pd.Series, series_b: pd.Series) -> dict`
Performs Engle-Granger two-step cointegration test.
* **Returns:**
  ```python
  {
      "t_stat": float,
      "p_value": float,
      "critical_values": {"1%": float, "5%": float, "10%": float},
      "cointegrated": bool,
      "is_cointegrated": bool
  }
  ```

#### `compute_spread_zscore(series_a: pd.Series, series_b: pd.Series, window: int = 60) -> pd.Series`
Computes rolling Z-score of log price spread $S_t = \ln(P_A) - \ln(P_B)$:
$$Z_t = \frac{S_t - \mu_t}{\sigma_t}$$

#### `ou_half_life(spread: pd.Series) -> float`
Estimates mean-reversion half-life ($t_{1/2}$) of the spread via AR(1) OLS regression:
$$t_{1/2} = -\frac{\ln 2}{\theta}$$
Returns `float('inf')` if $\theta \ge 0$ (non-reverting).

---

### `engine.portfolio`

#### `compute_beta_neutral_weights(beta_long: float, beta_short: float) -> dict`
Solves for weights that zero out portfolio beta while standardizing gross leverage to $100\%$:
$$w_L = \frac{\beta_S}{\beta_L + \beta_S}, \quad w_S = -\frac{\beta_L}{\beta_L + \beta_S}$$
* **Returns:** `{"long": float, "short": float, "w_long": float, "w_short": float}`

#### `convert_to_fno_lots(weights: dict, capital: float, lot_sizes: dict, prices: dict) -> dict`
Converts target percentage weights into integer NSE F&O contracts with margin and friction analysis.

#### `compute_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame`
Calculates the pairwise Pearson correlation matrix across all return series.

---

### `engine.backtester`

#### `calc_metrics(returns: pd.Series, market_returns: pd.Series, rf_rate: float = 0.068) -> dict`
Computes institutional performance metrics:
* Total Cumulative Return (`%`)
* Maximum Drawdown (`%`)
* Annualized Volatility (`%`)
* Annualized Sharpe Ratio ($R_f = 6.8\%$)
* Annualized Sortino Ratio
* Realized Ex-Post Beta
* Historical Value at Risk ($\text{VaR}_{95\%}$)
* Daily Cumulative Return Series

#### `backtest_pair(long_returns: pd.Series, short_returns: pd.Series, market_returns: pd.Series, w_long: float, w_short: float, rf_rate: float = 0.068) -> dict`
Simulates daily returns for both Unhedged (100% Long) and Beta-Neutral Hedged portfolios, returning comparative metrics and equity curves.

#### `stress_test(long_ticker: str, short_ticker: str, benchmark: str, regime: str) -> dict`
Executes backtest over predefined black swan crash periods:
* `"COVID_2020"` (2020-01-01 to 2020-06-30)
* `"2008_GFC"` (2008-01-01 to 2009-03-31)
* `"TECH_SELLOFF_2022"` (2022-01-01 to 2022-12-31)
* `"ELECTION_2024"` (2024-05-15 to 2024-06-15)

---

### `engine.verifier`

#### `verify_pair(pair_metrics: dict, unhedged_stats: dict, hedged_stats: dict, ...) -> dict`
Adversarial gatekeeper. Evaluates pair against four institutional guardrails:
1. `correlation >= 0.65`
2. `cointegration_pvalue < 0.05`
3. `hedged_mdd < 0.50 * unhedged_mdd`
4. `abs(realized_beta) < 0.15`
* **Returns:** `{"passed": bool, "approved": bool, "failed_checks": list, "diagnostic": str}`

#### `score_candidate(fundamentals: dict) -> float`
Computes composite fundamental score from ROE ($30\%$), Revenue Growth ($30\%$), Inverse PE ($20\%$), and Inverse Debt-to-Equity ($20\%$).

---

### `engine.hedge_pipeline`

#### `run_full_hedge_analysis(long_ticker: str, short_ticker: str, benchmark: str, start_date: str, end_date: str, capital: float = 100_000) -> dict`
Single master pipeline function orchestrating data ingestion, statistical modeling, portfolio sizing, backtesting, and verification.

---

## 2. Multi-Agent Orchestration (`agents/`)

### `agents.state.HedgeBuilderState`
Pydantic model carrying graph execution context across all nodes. Extends `langgraph.graph.MessagesState`. Key attributes:
* `thesis: str`: User input thesis.
* `target_sector: str`: Sector index name.
* `selected_long: str`: Long ticker symbol.
* `selected_short: str`: Short ticker symbol.
* `pair_metrics: dict`: Beta, correlation, cointegration.
* `weights: dict`: Long and short position weights.
* `unhedged_stats: dict`: Unhedged performance metrics.
* `hedged_stats: dict`: Hedged performance metrics.
* `rejection_log: list[dict]`: Complete history of rejected pairs.
* `attempt_count: int`: Current iteration loop count.
* `approved: bool`: Approval status flag.
* `cro_report: str`: Markdown executive memo.

### `agents.graph`

#### `build_graph() -> StateGraph`
Compiles the cyclical LangGraph workflow consisting of `macro_parser`, `screener`, `quant_engine`, `risk_verifier`, and `cro_reporter`.

#### `run_hedge_builder(thesis: str, benchmark: str = "^NSEI", lookback_days: int = 252, stress_regime: str = "COVID_2020", max_attempts: int = 5) -> dict`
Top-level entry point to run the entire multi-agent pipeline from natural language prompt to finalized tear-sheet.

---

## 3. User Interface (`ui/`)

### `ui.components`
* `render_metric_card(label, unhedged_val, hedged_val, format_str, invert=False)`: Displays before/after metrics with directional color styling.
* `render_agent_trace(rejection_log, approved)`: Renders collapsible execution and self-correction timeline.
* `render_fno_table(fno_data)`: Renders institutional lot contract allocation table.

### `ui.charts`
* `create_cumulative_returns_figure(unhedged_series, hedged_series, benchmark_series, regime_name)`: Plotly comparison chart.
* `create_rolling_beta_figure(rolling_beta)`: Plotly rolling beta time series with neutrality zero-line.
* `create_zscore_figure(zscore_series)`: Plotly spread Z-score with $\pm 1.5\sigma$ statistical entry bands.
* `create_correlation_heatmap_figure(corr_matrix)`: Plotly sector correlation heatmap.
