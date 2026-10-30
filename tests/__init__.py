"""
Tests for the Market-Neutral Hedge Builder Quant Engine.

Tests cover:
- Beta computation (static, EWMA, rolling)
- Cointegration analysis (Engle-Granger, spread Z-score, OU half-life)
- Portfolio construction (beta-neutral weights, F&O lot conversion)
- Backtesting (metrics calculation, stress testing)
- Verification guardrails
"""
