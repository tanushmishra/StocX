# 🛡️ Market-Neutral Hedge Builder

> **Autonomous Multi-Agent System with Zero-Hallucination Quantitative Finance Engine**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A hackathon-winning multi-agent system that constructs **beta-neutral long/short equity pairs** on the Indian stock market (NSE). The system uses **LLMs for qualitative reasoning** (macro analysis, stock screening, risk reporting) and **deterministic Python tools for all quantitative math** (covariance, cointegration, backtesting)—ensuring **zero numerical hallucination**.

<p align="center">
  <img src="docs/assets/architecture_diagram.png" alt="Architecture Diagram" width="800">
</p>

---

## 🎯 What It Does

You type a natural language investment thesis like:

> *"I'm bullish on Indian IT services but terrified of a US recession crashing the market"*

The system autonomously:

1. **Parses** your intent → identifies sector (NIFTY IT), benchmark (NIFTY 50), and stress regime (2020 COVID crash)
2. **Screens** all sector stocks on fundamentals (ROE, PE, revenue growth) → picks strongest Long & weakest Short
3. **Computes** exact Beta, correlation, cointegration, and beta-neutral weights via deterministic Python
4. **Verifies** the pair against strict guardrails (correlation > 0.65, cointegration p < 0.05, drawdown reduction > 50%)
5. **Self-corrects** by rejecting bad pairs and looping back to try the next best candidate
6. **Reports** a professional CRO tear sheet with before/after metrics and F&O execution plan

**The result:** A mathematically proven hedge that survived the March 2020 crash with a 4% drawdown instead of 29%.

---

## 📐 The Core Math

### Beta-Neutral Portfolio Construction

Given a Long stock with beta $\beta_L$ and a Short stock with beta $\beta_S$, the system solves:

$$w_L = \frac{\beta_S}{\beta_L + \beta_S}, \quad w_S = -\frac{\beta_L}{\beta_L + \beta_S}$$

This ensures **net portfolio beta = 0**, making the portfolio immune to market-wide moves.

**Example:** If $\beta_L = 0.80$ and $\beta_S = 1.20$:
- Long weight: $w_L = 1.20 / 2.00 = +60\%$
- Short weight: $w_S = -0.80 / 2.00 = -40\%$
- Portfolio beta: $(0.60 × 0.80) + (-0.40 × 1.20) = 0.00$ ✅

### Key Quantitative Models

| Model | Purpose | Implementation |
|-------|---------|----------------|
| **EWMA Beta** (λ=0.94) | Adaptive hedge ratios | `pandas.Series.ewm` |
| **Engle-Granger Cointegration** | Prove spread is stationary | `statsmodels.tsa.stattools.coint` |
| **Ornstein-Uhlenbeck Half-Life** | Mean-reversion speed | AR(1) via `statsmodels.OLS` |
| **Historical VaR (95%)** | Worst-case daily loss | `numpy.percentile` |
| **Sortino Ratio** | Downside-only risk-adjusted return | Custom vectorized |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                          │
│                                                                  │
│  ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐  │
│  │  Macro   │───▶│ Screener  │───▶│  Quant   │───▶│  Risk    │  │
│  │  Parser  │    │  Agent    │    │  Engine  │    │ Verifier │  │
│  │ (Flash)  │    │ (Flash)   │    │ (Python) │    │  (Pro)   │  │
│  └──────────┘    └───────────┘    └──────────┘    └──────────┘  │
│                       ▲                                │         │
│                       │           REJECTED             │         │
│                       └────────────────────────────────┘         │
│                                                                  │
│                                   APPROVED                       │
│                                      │                           │
│                               ┌──────────┐                      │
│                               │   CRO    │                      │
│                               │ Reporter │                      │
│                               │  (Pro)   │                      │
│                               └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### The Golden Rule

> **LLMs never guess numbers. Math models never read the news.**

| Component | Role | Technology |
|-----------|------|------------|
| Macro Parser | Understands natural language thesis | Gemini 2.5 Flash |
| Screener | Evaluates companies qualitatively | Gemini 2.5 Flash |
| Quant Engine | Computes exact math (Beta, covariance, weights) | Pure Python (numpy/pandas/scipy) |
| Risk Verifier | Interprets results & decides pass/fail | Gemini 2.5 Pro |
| CRO Reporter | Writes institutional-grade report | Gemini 2.5 Pro |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key ([Get one free](https://aistudio.google.com/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/your-team/market-neutral-hedge-builder.git
cd market-neutral-hedge-builder

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
copy .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Run the Dashboard

```bash
streamlit run app.py
```

### Run from CLI

```python
from agents.graph import run_hedge_builder

result = run_hedge_builder("Bullish on Indian IT, bearish on Wipro specifically")
print(result["cro_report"])
```

---

## 📁 Project Structure

```
market-neutral-hedge-builder/
├── app.py                      # Streamlit dashboard entry point
├── config.py                   # Global configuration & constants
├── pyproject.toml              # Project metadata & dependencies
├── .env.example                # Environment variable template
├── .gitignore
│
├── engine/                     # 🔢 Deterministic Quant Engine (NO LLMs)
│   ├── __init__.py
│   ├── data_fetcher.py         # yfinance data download & caching
│   ├── beta_calculator.py      # Static, EWMA, and rolling Beta
│   ├── cointegration.py        # Engle-Granger, spread Z-score, OU half-life
│   ├── portfolio.py            # Beta-neutral weight solver & F&O lots
│   ├── backtester.py           # Stress testing & performance metrics
│   ├── verifier.py             # Adversarial guardrail checks
│   └── hedge_pipeline.py       # Orchestrates full analysis pipeline
│
├── agents/                     # 🤖 LangGraph Multi-Agent System
│   ├── __init__.py
│   ├── state.py                # Pydantic state schema
│   ├── macro_parser.py         # Natural language → structured params
│   ├── screener.py             # Fundamental & catalyst screening
│   ├── quant_node.py           # Deterministic tool node (NO LLM)
│   ├── risk_verifier.py        # Adversarial pass/fail verification
│   ├── cro_reporter.py         # Executive summary generation
│   └── graph.py                # LangGraph StateGraph definition
│
├── ui/                         # 🎨 Streamlit UI Components
│   ├── __init__.py
│   ├── components.py           # Reusable UI widgets
│   ├── charts.py               # Plotly chart factories
│   └── styles.py               # CSS styling
│
├── tests/                      # ✅ Unit Tests
│   ├── __init__.py
│   ├── test_beta_calculator.py
│   ├── test_portfolio.py
│   ├── test_cointegration.py
│   └── test_verifier.py
│
├── data_cache/                 # 📦 Cached yfinance CSVs (gitignored)
│
└── docs/                       # 📚 Documentation
    ├── ARCHITECTURE.md          # Detailed architecture guide
    ├── QUANT_MODELS.md          # Mathematical model documentation
    ├── AGENTS.md                # Agent system documentation
    ├── API_REFERENCE.md         # Module & function reference
    ├── DEPLOYMENT.md            # Deployment & demo guide
    ├── CONTRIBUTING.md          # Contribution guidelines
    └── assets/                  # Diagrams and images
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=engine --cov=agents --cov-report=html

# Run specific test module
pytest tests/test_beta_calculator.py -v

# Run data engineering validation tests
pytest tests/test_download_historical_data.py -v
```

---

## 💾 Data Engineering & Historical Datasets

The project uses authentic market data stored in `data/` adhering to the StocX Data Contract (no synthetic data, missing prices strictly preserved as `NaN`, `Date` first, benchmark `^NSEI` last).

### Running Historical Data Ingestion
```bash
# Ingest or audit all 24 historical sector/regime datasets sequentially
python scripts/execute_phase1_loop.py

# Ingest a single sector and regime programmatically
python -c "from scripts.download_historical_data import download_sector_regime; download_sector_regime('NIFTY_BANK', 'COVID_2020')"

# Fetch/refresh current company fundamentals
python scripts/download_fundamentals.py

# Fetch/refresh official NSE F&O lot sizes from NSE India
python scripts/download_nse_lot_sizes.py
```

### Generated Datasets & Specifications
- **Historical Prices:** `data/<SECTOR>__<regime>.csv` (24 files covering 6 sectors × 4 historical stress regimes).
- **Fundamentals:** `data/fundamentals_2026-10-30.csv` (51 companies with separate `trailing_pe` and `forward_pe`).
- **F&O Lot Sizes:** `data/nse_lot_sizes.csv` (46 matched NSE derivative lots, near-month `NOV-26`).
- **Comprehensive Audit:** [data/PHASE_1_DATA_AUDIT.md](data/PHASE_1_DATA_AUDIT.md)
- **Data Dictionary:** [data/DATA_DICTIONARY.md](data/DATA_DICTIONARY.md)
```

---

## 📊 Sample Output

### Before vs After Metrics (TCS Long / Wipro Short, COVID 2020)

| Metric | Unhedged (100% TCS) | Hedged (Beta-Neutral) | Improvement |
|--------|---------------------|----------------------|-------------|
| Portfolio Beta | 1.12 | 0.02 | -98.2% |
| Max Drawdown | -28.4% | -4.1% | +85.6% |
| Sharpe Ratio | 0.65 | 1.84 | +183.1% |
| Sortino Ratio | 0.72 | 2.91 | +304.2% |
| VaR (95%) | -3.2% | -0.8% | +75.0% |
| Annual Volatility | 32.1% | 8.4% | -73.8% |

---

## 🏆 Hackathon Differentiators

1. **Self-Correcting Agent Loop** — The Verifier rejects bad pairs and the system retries automatically
2. **Zero-Hallucination Math** — Every number computed by deterministic Python, never by LLM
3. **Black Swan Time Machine** — One-click stress testing across 4 historical crashes
4. **Indian Market Realism** — F&O lot sizes, STT, and brokerage friction
5. **Dynamic Rebalancing** — EWMA Kalman-style rolling beta vs static hedge comparison

---

## 📄 Documentation

| Document | Description |
|----------|-------------|
| [Architecture Guide](docs/ARCHITECTURE.md) | System design, agent flow, and state management |
| [Quant Models](docs/QUANT_MODELS.md) | Mathematical models with derivations |
| [Agent System](docs/AGENTS.md) | LangGraph agent specifications |
| [API Reference](docs/API_REFERENCE.md) | Module and function documentation |
| [Deployment Guide](docs/DEPLOYMENT.md) | Setup, demo, and pitch guide |
| [Contributing](docs/CONTRIBUTING.md) | Code standards and contribution workflow |

---

## ⚠️ Disclaimer

This project is built for **educational and hackathon demonstration purposes only**. It does not constitute financial advice. The authors are not SEBI-registered advisors. Past performance in backtests does not guarantee future results. Always consult a qualified financial advisor before making investment decisions.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
