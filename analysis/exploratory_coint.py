"""Exploratory cointegration analysis: 2-year pre-event estimation window vs. original short window."""

import os
import sys
import time

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
import yfinance as yf

os.makedirs("scratch_data/exploratory", exist_ok=True)

# List of top pairs to evaluate
pairs = [
    # NIFTY_IT
    {"sector": "NIFTY_IT", "long": "WIPRO.NS", "short": "TCS.NS", "window": "election_2024", "orig_p": 0.0399},
    {"sector": "NIFTY_IT", "long": "MPHASIS.NS", "short": "TECHM.NS", "window": "covid_2020", "orig_p": 0.0377},
    {"sector": "NIFTY_IT", "long": "INFY.NS", "short": "TCS.NS", "window": "election_2024", "orig_p": 0.9518},
    {"sector": "NIFTY_IT", "long": "LTTS.NS", "short": "HCLTECH.NS", "window": "election_2024", "orig_p": 0.0106},
    {"sector": "NIFTY_IT", "long": "HCLTECH.NS", "short": "LTTS.NS", "window": "election_2024", "orig_p": 0.0289},
    # NIFTY_BANK
    {"sector": "NIFTY_BANK", "long": "BANKBARODA.NS", "short": "SBIN.NS", "window": "election_2024", "orig_p": 0.6239},
    {"sector": "NIFTY_BANK", "long": "IDFCFIRSTB.NS", "short": "AUBANK.NS", "window": "covid_2020", "orig_p": 0.0247},
    {"sector": "NIFTY_BANK", "long": "PNB.NS", "short": "BANKBARODA.NS", "window": "covid_2020", "orig_p": 0.0194},
    {"sector": "NIFTY_BANK", "long": "HDFCBANK.NS", "short": "KOTAKBANK.NS", "window": "covid_2020", "orig_p": 0.4145},
    {"sector": "NIFTY_BANK", "long": "BANKBARODA.NS", "short": "SBIN.NS", "window": "covid_2020", "orig_p": 0.4812},
    # NIFTY_AUTO
    {"sector": "NIFTY_AUTO", "long": "EICHERMOT.NS", "short": "TVSMOTOR.NS", "window": "covid_2020", "orig_p": 0.0162},
    {"sector": "NIFTY_AUTO", "long": "HEROMOTOCO.NS", "short": "BAJAJ-AUTO.NS", "window": "covid_2020", "orig_p": 0.1151},
    {"sector": "NIFTY_AUTO", "long": "TVSMOTOR.NS", "short": "EICHERMOT.NS", "window": "covid_2020", "orig_p": 0.0060},
    {"sector": "NIFTY_AUTO", "long": "BAJAJ-AUTO.NS", "short": "HEROMOTOCO.NS", "window": "covid_2020", "orig_p": 0.8685},
    {"sector": "NIFTY_AUTO", "long": "MARUTI.NS", "short": "BAJAJ-AUTO.NS", "window": "covid_2020", "orig_p": 0.0393},
    # NIFTY_PHARMA
    {"sector": "NIFTY_PHARMA", "long": "DRREDDY.NS", "short": "SUNPHARMA.NS", "window": "election_2024", "orig_p": 0.0047},
    {"sector": "NIFTY_PHARMA", "long": "DRREDDY.NS", "short": "DIVISLAB.NS", "window": "covid_2020", "orig_p": 0.0013},
    {"sector": "NIFTY_PHARMA", "long": "TORNTPHARM.NS", "short": "DIVISLAB.NS", "window": "covid_2020", "orig_p": 0.0431},
    {"sector": "NIFTY_PHARMA", "long": "AUROPHARMA.NS", "short": "APOLLOHOSP.NS", "window": "covid_2020", "orig_p": 0.6426},
    {"sector": "NIFTY_PHARMA", "long": "BIOCON.NS", "short": "SUNPHARMA.NS", "window": "election_2024", "orig_p": 0.6700},
]

# Dates for 2-year estimation windows ending at same pre-event date
WINS_2Y = {
    "covid_2020": {
        "start": "2018-02-01",
        "end": "2020-01-31",
        "desc": "2y pre-COVID (2018-02-01 to 2020-01-31)",
    },
    "election_2024": {
        "start": "2022-05-15",
        "end": "2024-05-15",
        "desc": "2y pre-Election (2022-05-15 to 2024-05-15)",
    },
}

def fetch_series(ticker: str, start: str, end: str) -> pd.Series:
    cache_file = f"scratch_data/exploratory/{ticker.replace('.','_')}_{start}_{end}.csv"
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["Date"]).set_index("Date")
        return df["Close"]

    for attempt in range(4):
        try:
            time.sleep(1.0)
            data = yf.download(
                ticker,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
            )
            if data is not None and not data.empty:
                close = data["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                close = close.dropna()
                if len(close) > 10:
                    df = close.to_frame(name="Close")
                    df.to_csv(cache_file)
                    return close
        except Exception as e:
            print(f"Retry {attempt+1} for {ticker}: {e}")
            time.sleep(2.0)
    raise RuntimeError(f"Failed to fetch data for {ticker}")

print("Fetching real market data for 2-year estimation windows...")
results = []

for item in pairs:
    win = item["window"]
    w_cfg = WINS_2Y[win]
    long_t = item["long"]
    short_t = item["short"]

    s_long = fetch_series(long_t, w_cfg["start"], w_cfg["end"])
    s_short = fetch_series(short_t, w_cfg["start"], w_cfg["end"])

    aligned = pd.concat({"long": s_long, "short": s_short}, axis=1).dropna()
    n_bars = len(aligned)

    if n_bars >= 20 and (aligned["long"] > 0).all() and (aligned["short"] > 0).all():
        log_l = np.log(aligned["long"])
        log_s = np.log(aligned["short"])
        t_stat, p_val_2y, _ = coint(log_l, log_s, trend="c")
        p_val_2y = float(p_val_2y)
    else:
        p_val_2y = float("nan")

    results.append({
        "sector": item["sector"],
        "pair": f"{long_t} / {short_t}",
        "window": win,
        "n_bars_2y": n_bars,
        "orig_p": item["orig_p"],
        "p_val_2y": round(p_val_2y, 4),
        "pass_orig": item["orig_p"] < 0.05,
        "pass_2y": p_val_2y < 0.05,
    })

res_df = pd.DataFrame(results)
print("\n" + "=" * 90)
print("EXPLORATORY COINTEGRATION COMPARISON: ORIGINAL (~7 MO) vs. 2-YEAR PRE-EVENT ESTIMATION")
print("=" * 90)
for idx, r in res_df.iterrows():
    orig_str = f"{r['orig_p']:.4f} ({'PASS' if r['pass_orig'] else 'FAIL'})"
    new_str = f"{r['p_val_2y']:.4f} ({'PASS' if r['pass_2y'] else 'FAIL'})"
    print(f"{r['sector']:<14} | {r['pair']:<28} | {r['window']:<14} | Orig (~7mo): {orig_str:<15} | 2-Year: {new_str:<15} | Bars: {r['n_bars_2y']}")

res_df.to_csv("scratch_data/exploratory/exploratory_coint_results.csv", index=False)
