# Market-Neutral Hedge Builder: Pitch & Presentation Guide

**Author:** Tanush (Lead Developer & Builder)  
**Tone:** Institutional, Mathematically Honest, Zero Hype  
**Rule:** No emojis. Strict Plain Text.

---

## 1. 60-Second Core Pitch (142 words | ~57 seconds at 150 wpm)

Large language models are exceptional at reasoning, but notorious for hallucinating financial numbers. In quantitative trading, a hallucinated beta or fake cointegration p-value destroys real capital.

We built the Market-Neutral Hedge Builder to solve this with an architectural firewall. An LLM parses the investor's macro thesis and screens fundamental candidates, but it is strictly forbidden from computing numbers. All financial math—OLS betas, RiskMetrics EWMA, Engle-Granger cointegration, and downside drawdown—is computed by a deterministic Python quant engine.

Every pair is then challenged by an Adversarial Verifier across historical black swans like COVID-19 and the 2008 GFC. If a pair violates any of four strict mathematical gates, it is rejected immediately. In our 1,356 sweep tests, zero pairs passed all four gates simultaneously—proving our verifier eliminates false-positive hedges rather than giving traders dangerous false confidence.

Hosted with Supabase authentication, paper trading, and Razorpay test billing.

---

## 2. 40-Second Lightning Cut (96 words | ~38 seconds at 150 wpm)

Most AI trading apps ask LLMs to pick stocks and calculate risk. That guarantees numerical hallucination.

The Market-Neutral Hedge Builder decouples reasoning from math. The AI agent interprets macroeconomic views and identifies sector candidates. A pure Python quantitative engine then calculates exact beta-neutral weights and runs Engle-Granger cointegration tests.

Next, an Adversarial Verifier stress-tests the hedge against historical crises. If correlation breaks, beta drifts, or drawdown reduction is weak, the hedge is rejected. Zero pairs out of 1,356 tests passed all four gates on baseline thresholds.

Honest quantitative risk engineering, built for the Indian market.

---

## 3. 3-Minute Live Evaluation Demo Walkthrough

### 0:00 - 0:30 | Authentication & Architecture
- Open the dashboard. Point out the hosted login gate powered by Supabase Auth with standard email/password and OTP verification.
- Click "Continue as Guest Demo Account" for instantaneous evaluation access.
- Point out the persistent status badge: `DELAYED (yfinance) | Paper Trading Only`. Explain that all pricing is delayed and live trading is disabled.

### 0:30 - 1:15 | Thesis Input & Execution Trace
- Enter the sample thesis: `"Bullish on Indian IT companies but want protection against a broad market crash"`.
- Set Lookback to 1Y (or 2Y for exploratory parity), Capital to INR 100,000, Benchmark to `^NSEI`.
- Click **Build Hedge**.
- Expand the **Multi-Agent Execution Audit Trail**. Show the deterministic sequence:
  1. `macro_parser`: Extracts sector and directional bias.
  2. `screener`: Matches fundamentals, gracefully excluding tickers with missing data (e.g. LTIM.NS).
  3. `quant_node`: Deterministic OLS beta sizing ($w_L, w_S$).
  4. `risk_verifier`: Four mathematical gates evaluated out-of-sample.
  5. `cro_reporter`: Institutional risk memo synthesis.

### 1:15 - 2:00 | Adversarial Gate Verification & Zero-Hallucination Rejection
- Scroll to the **Adversarial Risk Gate Verification** tear-sheet.
- Show the four independent gates:
  - Correlation Gate ($\ge 0.65$)
  - Cointegration Gate ($p < 0.05$)
  - Drawdown Gate (Hedged MDD $< 50\%$ of unhedged)
  - Beta Neutrality ($|\beta| < 0.15$)
- Walk through the result: If the verdict is `REJECTED`, highlight that this is an honest, institutional outcome. Show the specific criteria that failed (e.g. cointegration $p = 0.4145$ or correlation $0.45$).

### 2:00 - 2:40 | Paper Broker & Human Confirmation Flow
- Scroll to the **Paper Trading Execution & Portfolio Ledger**.
- Demonstrate the zero-hallucination guardrail:
  - If the pair was rejected: The system displays a clear warning and refuses to propose or dispatch orders.
  - If approved: The system proposes a long equity cash leg and a short leg sized to official NSE F&O futures contracts (e.g. WIPRO lot size 1500).
  - Emphasize that no order is EVER placed without explicit human confirmation. Show the "Confirm & Execute Paper Orders" button, Decimal cash ledger, and emergency Kill Switch.

### 2:40 - 3:00 | Razorpay Test Mode & Tier Gating
- Click "Upgrade to Premium" in the sidebar.
- Show the prominent **RAZORPAY TEST MODE** banner. Explain that live keys are blocked at runtime.
- Click the Test Mode checkout simulator to demonstrate HMAC-SHA256 signature verification and anti-replay protection, unlocking unlimited runs.

---

## 4. Top 10 Honest Judge Questions & Answers

### Q1: Why did zero pairs pass all four verification gates in your 1,356 sweep?
**A:** Because our verifier is genuinely adversarial. Most trading platforms tune thresholds downwards until pairs pass so they have something to show. We refused to relax our institutional thresholds (correlation $\ge 0.65$, cointegration $p < 0.05$, drawdown cut $> 50\%$, and $|\beta| < 0.15$). In emerging markets like India, true stationary cointegration over a short 7-month window is extremely rare. An all-rejected verdict is a mathematically honest result that protects capital from false-positive hedges.

### Q2: Why does an extended 2-year lookback change the cointegration result for HDFC / Kotak?
**A:** Engle-Granger ADF tests have low statistical power when $N < 200$ bars. Over 7 months, localized divergence looks like a random walk ($p = 0.4145$). When expanding to 2 years ($489$ bars), the long-term structural parity between India's top private banks becomes evident, dropping $p$ to $0.0333$. We document this transparently in `docs/SHOWCASE_PAIRS.md` as an exploratory post-hoc study, while keeping default thresholds untouched in production.

### Q3: What prevents the LLM from hallucinating numbers in the CRO memo or UI?
**A:** The LLM prompt never receives mathematical tasks. All metrics are computed by Python functions in `engine/` using `numpy`, `scipy`, and `statsmodels`. Computed numbers are injected into the LLM context as read-only strings for narrative summarization, and the Streamlit dashboard reads values directly from the structured Python ViewModel, completely bypassing LLM output text.

### Q4: Why are short legs sized using F&O futures lot sizes?
**A:** On the National Stock Exchange of India (NSE), short selling in the equity cash segment is restricted to intraday trading only. Overnight equity short positions are prohibited by SEBI regulations. Therefore, any statistical hedge held overnight must execute the short leg via NSE stock futures, which trade in fixed contract lot sizes (e.g. TCS = 175, WIPRO = 1500).

### Q5: How do you handle missing fundamentals or API 404s like LTIM.NS?
**A:** We never substitute missing data with artificial zeros. When a constituent like LTIM.NS returns HTTP 404 or lacks fundamentals, the screener logs a descriptive warning, records the exclusion in the audit trail, and evaluates the next available peer without crashing.

### Q6: Can a user connect a real broker and trade real money?
**A:** No. Live trading is strictly disabled. The architecture implements an abstract `BrokerAdapter` interface, but the production class is `PaperBroker`. The `LiveBrokerStub` explicitly raises `NotImplementedError`. We never request broker credentials, and all executions are simulated on virtual cash.

### Q7: Why use Python Decimal instead of float for paper broker accounting?
**A:** Standard IEEE-754 floating-point math introduces binary rounding drift (e.g. $0.1 + 0.2 = 0.30000000000000004$). For an institutional ledger tracking cash, weighted average costs, and realized P&L, cumulative rounding errors corrupt ledger reconciliation. Decimal guarantees exact currency precision.

### Q8: How does your Razorpay integration prevent unpaid account upgrades?
**A:** We verify payments server-side using cryptographic HMAC-SHA256 signatures generated with `RAZORPAY_KEY_SECRET`. The client cannot self-upgrade by toggling local state. In addition, every redeemed `payment_id` is recorded in an anti-replay set so that a transaction ID cannot be reused.

### Q9: What happens if Gemini API quota is exhausted or times out?
**A:** The system implements a loud fallback. If the Gemini API returns a 429 quota exhaustion or network timeout, the pipeline falls back to deterministic heuristic parsing and screening, while displaying a prominent warning: `"LLM unavailable: heuristic defaults used"`. The quant engine and verifier continue running with 100% mathematical integrity.

### Q10: How do you enforce data isolation between multiple users?
**A:** We use Supabase Row Level Security (RLS) on every table (`profiles`, `runs`, `paper_accounts`, `orders`, `positions`, `risk_limits`, `payments`, `audit_log`). Every query executes with the user's JWT, enforcing `auth.uid() = user_id` at the PostgreSQL engine level. The service-role key is never included in client code.
