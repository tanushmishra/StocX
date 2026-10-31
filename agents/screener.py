"""Fundamental & Catalyst Screener – LLM-augmented stock selection node.

This agent:

1. Pulls the sector constituent universe from ``engine.data_fetcher``.
2. Fetches fundamentals (PE, ROE, debt/equity, etc.) for every ticker.
3. Scores each stock with ``engine.verifier.score_candidate()`` to get a
   deterministic quality score, preserving data provenance.
4. Retrieves recent news and catalyst headlines via ``engine.news_fetcher``.
5. Uses **Gemini 2.5 Flash** with resilient retry handling to synthesise
   the fundamental scores and qualitative catalyst signals into a long/short
   pair recommendation.
6. On retries (``attempt_count > 0``), automatically *excludes* previously
   rejected pairs so the graph doesn't keep re-proposing the same pair.

The LLM is used **only** for ranking and narrative synthesis; all numerical
scores come from the deterministic engine.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.gemini_client import get_gemini_client, invoke_with_retry
from agents.state import HedgeBuilderState, StateProxy, wrap_state
from engine.data_fetcher import get_fundamentals, get_sector_constituents
from engine.news_fetcher import fetch_ticker_news, format_news_for_screener
from engine.verifier import score_candidate

logger = logging.getLogger(__name__)


def _get(state: Any, key: str, default: Any = None) -> Any:
    """Safely get an attribute or dictionary key from state."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# ────────────────────────────────────────────────────────────────────────────
# Structured output schema
# ───────────────────────────────────────────────────────────────────────────


class PairSelection(BaseModel):
    """LLM-produced long/short pair recommendation.

    Attributes:
        selected_long: Ticker symbol for the long leg.
        selected_short: Ticker symbol for the short leg.
        long_rationale: Why this stock is the strongest long candidate.
        short_rationale: Why this stock is the weakest / best short candidate.
        overall_reasoning: High-level synthesis tying the pair to the thesis.
    """

    selected_long: str = Field(description="NSE ticker for the long leg (e.g. 'INFY.NS').")
    selected_short: str = Field(description="NSE ticker for the short leg (e.g. 'WIPRO.NS').")
    long_rationale: str = Field(description="2-3 sentence justification for the long pick.")
    short_rationale: str = Field(description="2-3 sentence justification for the short pick.")
    overall_reasoning: str = Field(description="Brief paragraph connecting the pair to the thesis.")


# ────────────────────────────────────────────────────────────────────────────
# System prompt
# ────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are **FundScreenerGPT**, an expert Indian equity fundamental analyst.

You will receive:
1. A trading thesis.
2. A table of candidate stocks with their fundamental scores and data provenance
   (computed by a deterministic engine – treat these numbers as ground truth).
3. Recent news and catalyst headlines for screened candidates (if available).
4. A list of previously rejected long/short pairs (if any).

Your job:
- Select the STRONGEST stock as the **long** candidate.
- Select the WEAKEST stock as the **short** candidate.
- You MUST NOT select any pair that appears in the rejected list.
- Use fundamental scores as the primary selection criterion.
- Cross-reference news headlines for qualitative catalyst confirmation:
  positive operational momentum/guidance supports long picks; earnings misses,
  margin pressure, governance or regulatory issues support short picks.
- NEVER invent or recompute numerical metrics or fabricate news headlines.
"""


# ────────────────────────────────────────────────────────────────────────────
# Helper – build the candidate table string
# ────────────────────────────────────────────────────────────────────────────


def _format_candidates(candidates: list[dict]) -> str:
    """Format a list of scored candidate dicts into a readable markdown table."""
    if not candidates:
        return "_No candidates available._"

    headers = ["Ticker", "Score", "PE", "ROE", "Rev Growth", "D/E", "Data Source"]
    rows = []
    for c in candidates:
        ticker = c.get("ticker", "")
        score_val = c.get("score")
        score = f"{float(score_val):.2f}" if score_val is not None else "N/A"
        pe_val = c.get("pe_ratio")
        pe = f"{float(pe_val):.1f}" if pe_val is not None else "N/A"
        roe_val = c.get("roe")
        roe = f"{float(roe_val) * 100:.1f}%" if roe_val is not None else "N/A"
        rev_val = c.get("revenue_growth")
        rev = f"{float(rev_val) * 100:.1f}%" if rev_val is not None else "N/A"
        de_val = c.get("debt_to_equity")
        de = f"{float(de_val):.2f}" if de_val is not None else "N/A"
        ds = c.get("data_source", "fundamentals_csv")
        rows.append(f"| {ticker} | {score} | {pe} | {roe} | {rev} | {de} | {ds} |")

    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    return "\n".join([header_line, sep_line, *rows])


def _format_rejection_log(rejection_log: list[dict]) -> str:
    """Build a human-readable rejection history string."""
    if not rejection_log:
        return "_None – this is the first attempt._"

    lines: list[str] = []
    for i, entry in enumerate(rejection_log, 1):
        lines.append(
            f"{i}. **{entry.get('long', '?')}** / **{entry.get('short', '?')}** – "
            f"{entry.get('reason', 'no reason recorded')}"
        )
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
# Node function
# ────────────────────────────────────────────────────────────────────────────


def screener_node(state: HedgeBuilderState | dict[str, Any]) -> dict:
    """Screen sector constituents and select a long/short pair.

    Args:
        state: Current graph state containing ``target_sector``, ``thesis``,
            ``attempt_count``, and ``rejection_log``.

    Returns:
        Partial state dict updating ``sector_tickers``, ``long_candidates``,
        ``short_candidates``, ``selected_long``, ``selected_short``, and
        appending an assistant message with reasoning.
    """
    state = wrap_state(state)
    sector = state.target_sector or "NIFTY IT"
    thesis = state.thesis or ""
    attempt = int(state.attempt_count)
    max_attempts = int(state.max_attempts)
    rejection_log = state.rejection_log or []

    logger.info(
        "Screener ▸ Attempt %d | Sector: %s | Rejected pairs so far: %d",
        attempt + 1,
        sector,
        len(rejection_log),
    )

    # ── 1. Get sector universe ─────────────────────────────────────────
    try:
        sector_tickers: list[str] = get_sector_constituents(sector)
        logger.info("Screener ▸ Fetched %d tickers for %s", len(sector_tickers), sector)
    except Exception as exc:
        logger.error("Screener ▸ Failed to fetch sector constituents: %s", exc)
        sector_tickers = []

    # ── 2. Fetch fundamentals and score ────────────────────────────────
    all_candidates: list[dict] = []
    excluded_candidates: list[dict[str, str]] = []
    for ticker in sector_tickers:
        try:
            fundamentals: dict = get_fundamentals(ticker)
            score: float = score_candidate(ticker, fundamentals)
            candidate = {
                "ticker": ticker,
                "score": score,
                **fundamentals,
            }
            all_candidates.append(candidate)
        except (KeyError, ValueError):
            logger.warning("Screener ▸ Skipping candidate %s: Ticker %s excluded: no fundamentals data", ticker, ticker)
            excluded_candidates.append({"ticker": ticker, "reason": f"Ticker {ticker} excluded: no fundamentals data"})
            continue
        except Exception as exc:
            logger.warning("Screener ▸ Skipping candidate %s: %s", ticker, exc)
            excluded_candidates.append({"ticker": ticker, "reason": f"Ticker {ticker} excluded: {exc}"})
            continue

    # ── 3. Separate into long (high score) and short (low score) ───────
    sorted_candidates = sorted(all_candidates, key=lambda c: c.get("score", 0), reverse=True)

    # If thesis explicitly names any constituents, prioritize them in screening
    thesis_lower = (thesis or "").lower()
    explicit_long = []
    explicit_short = []
    general_mentioned = []

    for c in sorted_candidates:
        name = c.get("ticker", "").replace(".NS", "").lower()
        if name and name in thesis_lower:
            idx = thesis_lower.find(name)
            preceding = thesis_lower[max(0, idx - 25):idx]
            following = thesis_lower[idx + len(name):min(len(thesis_lower), idx + len(name) + 25)]
            if any(w in preceding for w in ["short", "bearish", "sell", "hedge with", "against"]):
                explicit_short.append(c)
            elif any(w in preceding for w in ["long", "bullish", "buy", "pair trade"]):
                explicit_long.append(c)
            elif any(w in following.split()[:2] for w in ["short", "bearish", "sell"]):
                explicit_short.append(c)
            elif any(w in following.split()[:2] for w in ["long", "bullish", "buy"]):
                explicit_long.append(c)
            else:
                general_mentioned.append(c)

    # If user mentioned multiple tickers without directional keywords, sort by score
    if not explicit_long and not explicit_short and len(general_mentioned) >= 2:
        general_mentioned.sort(key=lambda c: c.get("score", 0), reverse=True)
        explicit_long = [general_mentioned[0]]
        explicit_short = [general_mentioned[-1]]
    elif not explicit_long and general_mentioned:
        explicit_long = general_mentioned

    other_candidates = [c for c in sorted_candidates if c not in explicit_long and c not in explicit_short]
    midpoint = max(len(other_candidates) // 2, 1) if other_candidates else 0
    long_candidates = explicit_long + other_candidates[:midpoint]
    short_candidates = explicit_short + sorted(other_candidates[midpoint:], key=lambda c: c.get("score", 0))

    # ── 4. Build excluded pairs set for the LLM ───────────────────────
    excluded_pairs = {
        (entry["long"], entry["short"])
        for entry in rejection_log
        if "long" in entry and "short" in entry
    }

    # ── 5. Fetch recent news/catalysts for top candidates ──────────────
    top_tickers_to_query = list(
        dict.fromkeys(
            [c["ticker"] for c in long_candidates[:3]]
            + [c["ticker"] for c in short_candidates[:3]]
        )
    )
    news_map: dict[str, list[dict[str, Any]]] = {}
    for ticker in top_tickers_to_query:
        try:
            news_map[ticker] = fetch_ticker_news(ticker, max_results=2)
        except Exception as exc:
            logger.warning("Screener ▸ Failed news fetch for %s: %s", ticker, exc)
            news_map[ticker] = []

    news_section = format_news_for_screener(news_map)

    # ── 6. Ask LLM to select the pair ─────────────────────────────────
    user_content = (
        f"## Thesis\n{thesis}\n\n"
        f"## Attempt\n{attempt + 1} of {max_attempts}\n\n"
        f"## Long Candidates (sorted best→worst)\n"
        f"{_format_candidates(long_candidates)}\n\n"
        f"## Short Candidates (sorted worst→best)\n"
        f"{_format_candidates(short_candidates)}\n\n"
        f"## Recent News & Catalysts\n"
        f"{news_section}\n\n"
        f"## Previously Rejected Pairs (DO NOT re-select these)\n"
        f"{_format_rejection_log(rejection_log)}\n"
    )

    try:
        structured_llm = get_gemini_client(
            model_type="fast",
            temperature=0.3,
            structured_schema=PairSelection,
        )

        selection: PairSelection = invoke_with_retry(
            structured_llm,
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ],
        )
        selected_long = selection.selected_long
        selected_short = selection.selected_short
        reasoning = selection.overall_reasoning

        # ── Safety check: did the LLM accidentally pick a rejected pair?
        if (selected_long, selected_short) in excluded_pairs:
            logger.warning(
                "Screener ▸ LLM re-proposed a rejected pair (%s/%s). "
                "Falling back to top-scoring non-rejected candidates.",
                selected_long,
                selected_short,
            )
            selected_long, selected_short, reasoning = _fallback_selection(
                long_candidates, short_candidates, excluded_pairs
            )

        logger.info("Screener ▸ Selected LONG=%s  SHORT=%s", selected_long, selected_short)

    except Exception as exc:
        logger.error("Screener ▸ LLM selection failed (%s). Using deterministic fallback.", exc)
        selected_long, selected_short, reasoning = _fallback_selection(
            long_candidates, short_candidates, excluded_pairs
        )

    # ── 7. Build partial state update ──────────────────────────────────
    excluded_text = ""
    if excluded_candidates:
        excluded_lines = "\n".join(f"- {item['reason']}" for item in excluded_candidates)
        excluded_text = f"\n\n**Excluded Constituents:**\n{excluded_lines}"

    summary_msg = (
        f"**Screener – Attempt {attempt + 1}**\n\n"
        f"- **Long:** {selected_long}\n"
        f"- **Short:** {selected_short}\n\n"
        f"**Reasoning:** {reasoning}"
        f"{excluded_text}"
    )

    return {
        "sector_tickers": sector_tickers,
        "long_candidates": long_candidates,
        "short_candidates": short_candidates,
        "selected_long": selected_long,
        "selected_short": selected_short,
        "messages": [{"role": "assistant", "content": summary_msg}],
    }


# ────────────────────────────────────────────────────────────────────────────
# Deterministic fallback (no LLM)
# ────────────────────────────────────────────────────────────────────────────


def _fallback_selection(
    long_candidates: list[dict],
    short_candidates: list[dict],
    excluded: set[tuple[str, str]],
) -> tuple[str, str, str]:
    """Pick the best non-excluded long and worst non-excluded short.

    Orders search diagonally across long and short candidate pairs so retries
    vary both the long and short legs rather than exhausting all attempts on one stock.
    """
    pairs = []
    max_len = max(len(long_candidates), len(short_candidates))
    for diag in range(max_len * 2):
        for i in range(diag + 1):
            j = diag - i
            if i < len(long_candidates) and j < len(short_candidates):
                pairs.append((long_candidates[i], short_candidates[j]))

    for lc, sc in pairs:
        lt = lc.get("ticker", "")
        st = sc.get("ticker", "")
        if lt and st and (lt, st) not in excluded:
            return (
                lt,
                st,
                f"Deterministic selection: Long {lt} vs Short {st}.",
            )

    lt = long_candidates[0]["ticker"] if long_candidates else ""
    st = short_candidates[0]["ticker"] if short_candidates else ""
    return lt, st, "Last resort fallback."
