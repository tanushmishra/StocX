# 📐 Quantitative & Econometric Models

## 1. The ELI5 Intuition: The Ocean and the Boats

To understand why institutional hedge funds build market-neutral portfolios, consider this analogy:

* **The Ocean is the Benchmark Index (NIFTY 50):** The ocean rises and falls with tides, storms, and geopolitical tsunamis.
* **Individual Companies are Boats Floating on the Water:** Companies like **TCS**, **Infosys**, and **Wipro** are boats floating in the IT sector current.
* **The Problem with Long-Only Investing:** You do deep research and realize **TCS** has the strongest engineering team and best management (a great boat). You invest ₹1,00,000 going **Long**. Suddenly, a global macro black swan hits (like the March 2020 COVID crash). The entire ocean drops $38\%$. Even the best boat sinks, and your portfolio loses ₹30,000.
* **The Long/Short Hedge:** To protect yourself from the ocean, you find a competitor in the exact same water that has a weaker balance sheet or declining margins—say, **Wipro**—and you bet *against* it (going **Short**). When the ocean drops, your Long boat drops, but your Short bet generates profit, neutralizing the crash.
* **The Correlation Requirement:** You cannot hedge an IT company with a cement manufacturer. They float on completely different economic currents. You need two assets that share strong structural co-movement (Pearson correlation $\rho \ge 0.65$).
* **Beta ($\beta$) as the Bounce Factor:** Not all boats bounce equally when a wave hits:
  * If the ocean drops $10\%$ and Infosys drops $12\%$, Infosys has a Beta of **$1.20$**.
  * If TCS only drops $8\%$ when the ocean drops $10\%$, TCS has a Beta of **$0.80$**.
* **Beta-Neutral Sizing (The Magic Shield):** If you invest equal ₹50,000 on both, you are still exposed to market waves because Wipro bounces $50\%$ more than TCS. Sizing positions inversely proportional to their Betas cancels market sensitivity to exactly zero ($\beta_P = 0.00$). Whether the market rallies $20\%$ or crashes $30\%$, market drift cancels out, leaving pure **Alpha** ($\alpha$).

---

## 2. Capital Asset Pricing Model (CAPM) & Beta Derivation

Under the classical Sharpe-Lintner Capital Asset Pricing Model (CAPM), an asset's expected return is decomposed into systematic (market) risk and idiosyncratic (firm-specific) risk:

$$R_{i,t} - R_f = \alpha_i + \beta_i (R_{M,t} - R_f) + \epsilon_{i,t}$$

Where:
* $R_{i,t}$ is the daily return of stock $i$:
  $$R_{i,t} = \frac{P_{i,t} - P_{i,t-1}}{P_{i,t-1}}$$
* $R_{M,t}$ is the benchmark market return (NIFTY 50, `^NSEI`).
* $R_f$ is the daily risk-free rate derived from the RBI 10-Year Government Bond yield ($6.8\%$ annualized):
  $$R_{f,\text{daily}} = (1 + 0.068)^{1/252} - 1$$
* $\epsilon_{i,t}$ is the idiosyncratic error term with $\mathbb{E}[\epsilon_{i,t}] = 0$ and $\text{Cov}(\epsilon_{i,t}, R_{M,t}) = 0$.

Taking the covariance of asset return with market return:

$$\text{Cov}(R_i, R_M) = \text{Cov}(\alpha_i + \beta_i R_M + \epsilon_i, R_M) = \beta_i \text{Var}(R_M)$$

Solving for **Beta ($\beta_i$)**:

$$\beta_i = \frac{\text{Cov}(R_i, R_M)}{\text{Var}(R_M)} = \frac{\sum_{t=1}^T (R_{i,t} - \bar{R}_i)(R_{M,t} - \bar{R}_M)}{\sum_{t=1}^T (R_{M,t} - \bar{R}_M)^2}$$

---

## 3. Mathematical Derivation of Beta-Neutral Sizing

Let a two-asset long/short portfolio consist of weights $w_L$ (positive, Long) and $w_S$ (negative, Short). The portfolio's return is:

$$R_P = w_L R_L + w_S R_S$$

The portfolio's sensitivity to the market (Portfolio Beta, $\beta_P$) is:

$$\beta_P = \frac{\text{Cov}(R_P, R_M)}{\text{Var}(R_M)} = w_L \beta_L + w_S \beta_S$$

To achieve **strict market neutrality**, we impose the condition:

$$\beta_P = w_L \beta_L + w_S \beta_S = 0$$

Simultaneously, we standardize total gross leverage exposure to $100\%$ ($1.0$):

$$|w_L| + |w_S| = 1$$

Since $w_L > 0$ and $w_S < 0$, $|w_L| = w_L$ and $|w_S| = -w_S$. Therefore:

$$w_L - w_S = 1 \implies -w_S = 1 - w_L \implies w_S = -(1 - w_L)$$

Substitute $w_S$ into the neutrality equation:

$$w_L \beta_L - (1 - w_L) \beta_S = 0$$
$$w_L \beta_L - \beta_S + w_L \beta_S = 0$$
$$w_L (\beta_L + \beta_S) = \beta_S$$

Solving for $w_L$ and $w_S$:

$$w_L = \frac{\beta_S}{\beta_L + \beta_S}$$

$$w_S = -\frac{\beta_L}{\beta_L + \beta_S}$$

### Worked Example:
Assume:
* Long Candidate (TCS): $\beta_L = 0.80$
* Short Candidate (Wipro): $\beta_S = 1.20$
* Total Capital: ₹1,00,000

$$w_L = \frac{1.20}{0.80 + 1.20} = \frac{1.20}{2.00} = +0.60 \quad (+\text{₹}60,000 \text{ Long})$$
$$w_S = -\frac{0.80}{0.80 + 1.20} = -\frac{0.80}{2.00} = -0.40 \quad (-\text{₹}40,000 \text{ Short})$$

Verification of Portfolio Beta:
$$\beta_P = (0.60 \times 0.80) + (-0.40 \times 1.20) = 0.48 - 0.48 = 0.00 \quad \text{[Exact Neutrality]}$$

---

## 4. Exponentially Weighted Moving Average (EWMA) Beta

Static OLS betas assign equal weight to market shocks from 250 days ago and shocks from yesterday. In periods of market stress (e.g., March 2020), asset volatility surges instantly, causing static hedges to fail.

The system implements the institutional **RiskMetrics EWMA framework** with decay factor $\lambda = 0.94$:

$$\sigma^2_{M,t} = \lambda \sigma^2_{M,t-1} + (1 - \lambda) (R_{M,t} - \bar{R}_{M})^2$$
$$\sigma_{iM,t} = \lambda \sigma_{iM,t-1} + (1 - \lambda) (R_{i,t} - \bar{R}_i)(R_{M,t} - \bar{R}_M)$$

The dynamic EWMA Beta at time $t$ is:

$$\beta_{i,t}^{\text{EWMA}} = \frac{\sigma_{iM,t}}{\sigma^2_{M,t}}$$

This allows dynamic hedge rebalancing that adjusts position sizing as market regimes transition from low-volatility drifts to high-volatility crashes.

---

## 5. Engle-Granger Two-Step Cointegration Test

Correlation measures co-movement in returns, but returns can drift apart over time. **Cointegration** ensures that a linear combination of non-stationary price series forms a stationary equilibrium spread.

### Step 1: Cointegrating Regression
Estimate the equilibrium relationship between log prices via Ordinary Least Squares (OLS):

$$\ln(P_{A,t}) = \alpha + \gamma \ln(P_{B,t}) + \epsilon_t$$

Where $\gamma$ is the hedge ratio and $\epsilon_t$ is the residual spread:

$$\hat{\epsilon}_t = \ln(P_{A,t}) - \hat{\alpha} - \hat{\gamma} \ln(P_{B,t})$$

### Step 2: Augmented Dickey-Fuller (ADF) Unit Root Test
Test whether residuals $\hat{\epsilon}_t$ are stationary ($I(0)$) by estimating:

$$\Delta \hat{\epsilon}_t = \delta \hat{\epsilon}_{t-1} + \sum_{j=1}^p \phi_j \Delta \hat{\epsilon}_{t-j} + u_t$$

Null hypothesis $H_0: \delta = 0$ (unit root / non-stationary spread).
Alternative $H_1: \delta < 0$ (stationary / mean-reverting spread).

The test statistic is compared against MacKinnon critical values:
* $1\%$ critical value: $-3.90$
* $5\%$ critical value: $-3.34$
* $10\%$ critical value: $-3.04$

**Verification Rule:** The pair passes only if $p\text{-value} < 0.05$ ($t\text{-stat} < -3.34$).

---

## 6. Ornstein-Uhlenbeck (OU) Mean-Reversion Half-Life Model

If a spread is cointegrated, its dynamics follow a continuous-time Ornstein-Uhlenbeck process:

$$dS_t = \theta (\mu - S_t) dt + \sigma dW_t$$

Where:
* $S_t = \ln(P_{A,t}) - \ln(P_{B,t})$ is the price spread.
* $\theta > 0$ is the speed of mean reversion.
* $\mu$ is the long-term equilibrium spread.
* $\sigma$ is the spread volatility.
* $W_t$ is a standard Wiener process.

In discrete time, this is estimated via an autoregressive AR(1) regression:

$$\Delta S_t = S_t - S_{t-1} = \lambda S_{t-1} + c + e_t$$

Where $\lambda = -(1 - e^{-\theta \Delta t}) \approx -\theta$.

The **Half-Life ($t_{1/2}$)**—the expected time required for the spread to decay halfway back to equilibrium—is:

$$t_{1/2} = -\frac{\ln(2)}{\lambda}$$

*Interpretation:* If $t_{1/2} = 14$ days, deviations from mean are expected to revert by $50\%$ in two trading weeks. If $\lambda \ge 0$, the spread does not mean-revert ($t_{1/2} = \infty$).

---

## 7. Spread Z-Score Statistical Entry Signal

The system computes a rolling Z-score over lookback window $w = 60$ trading days:

$$Z_t = \frac{S_t - \text{MA}(S_t, w)}{\text{Std}(S_t, w)}$$

```
+2.0 σ ────────────────────────────────────── Overbought (Short Long Stock / Buy Short Stock)
+1.5 σ -------------------------------------- Statistically Optimal Entry Upper Bound
 0.0 σ ══════════════════════════════════════ Equilibrium Mean (Take Profit Zone)
-1.5 σ -------------------------------------- Statistically Optimal Entry Lower Bound
-2.0 σ ────────────────────────────────────── Oversold (Strong Buy Long Stock / Sell Short Stock)
```

* **$|Z_t| \ge 1.5$:** Statistically stretched; optimal timing to enter the beta-neutral pair.
* **$Z_t \to 0$:** Spread has converged back to equilibrium; exit or rebalance pair.

---

## 8. Institutional Risk & Backtest Metrics

### Maximum Drawdown (MDD)
Measures peak-to-trough capital decline over any historical window:

$$\text{MDD} = \min_{t} \left( \frac{\text{CumRet}_t - \max_{s \le t} \text{CumRet}_s}{\max_{s \le t} \text{CumRet}_s} \right)$$

### Annualized Sharpe Ratio
Risk-adjusted excess return over the risk-free rate:

$$\text{Sharpe} = \frac{\bar{R}_P \times 252 - R_f}{\sigma_P \times \sqrt{252}}$$

Where $R_f = 6.8\%$ (10-Year Indian Government Security yield).

### Annualized Sortino Ratio
Penalizes downside volatility only, ignoring positive upside volatility:

$$\text{Sortino} = \frac{\bar{R}_P \times 252 - R_f}{\sigma_{\text{downside}} \times \sqrt{252}}, \quad \sigma_{\text{downside}} = \sqrt{\frac{1}{T}\sum_{t=1}^T \min(0, R_{P,t} - R_f)^2}$$

### Historical Value at Risk ($\text{VaR}_{95\%}$)
Non-parametric 95th percentile worst expected single-day loss:

$$\text{VaR}_{95\%} = \text{Percentile}(R_{P}, 5\%)$$

### Realized Ex-Post Beta
Confirms actual portfolio beta across historical backtest periods:

$$\beta_{\text{realized}} = \frac{\text{Cov}(R_P, R_M)}{\text{Var}(R_M)}$$

---

## 9. Indian Market Institutional Realism (F&O & Friction)

### Overnight Equity Shorting Constraint
In the cash equity market (NSE/BSE), retail and institutional traders cannot carry short equity positions overnight. To implement institutional pair trading, trades must be executed through **NSE Equity Futures (F&O)**.

### Lot Sizing Formula
Given total portfolio capital $C$, target weights $w_L, w_S$, current spot prices $P_L, P_S$, and exchange-specified lot sizes $L_L, L_S$:

$$\text{Contract Value}_i = P_i \times L_i$$
$$\text{Number of Lots}_i = \text{round}\left( \frac{C \times |w_i|}{\text{Contract Value}_i} \right)$$

### F&O Friction Model
Execution drag is accounted for in all backtest performance reports:
* **Brokerage:** $0.10\%$ ($10\text{ bps}$)
* **Securities Transaction Tax (STT):** $0.0125\%$ on futures sell turnover
* **Goods and Services Tax (GST):** $18\%$ applied to brokerage
* **Exchange Turnover & Stamp Duty:** $0.005\%$
* **Net Round-Trip Friction:** $\approx 0.12\%$
