"""Fundamental & Catalyst Screener – LLM-augmented stock selection node.

This agent:

1. Pulls the sector constituent universe from ``engine.data_fetcher``.
2. Fetches fundamentals (PE, ROE, debt/equity, etc.) for every ticker.
3. Scores each stock with ``engine.verifier.score_candidate()`` to get a
   deterministic quality score.
4. Uses **Gemini 2.5 Flash** to synthesise the fundamental scores and any
   available news/sentiment signals into a long/short pair recommendation.
5. On retries (``attempt_count > 0``), automatically *excludes* previously
   rejected pairs so the graph doesn't keep re-proposing the same pair.

The LLM is used **only** for ranking and narrative synthesis; all numerical
scores come from the deterministic engine.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agents.state import HedgeBuilderState

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Structured output schema
# ────────────────────────────────────────────────────────────────────────────


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
2. A table of candidate stocks with their fundamental scores (computed by a
   deterministic engine – treat these numbers as ground truth).
3. A list of previously rejected long/short pairs (if any).

Your job:
- Select the STRONGEST stock as the **long** candidate.
- Select the WEAKEST stock as the **short** candidate.
- You MUST NOT select any pair that appears in the rejected list.
- Provide clear rationale grounded in the fundamental scores.
- Do NOT invent or recompute any numbers.  Only reference the scores given.
"""


# ────────────────────────────────────────────────────────────────────────────
# Helper – build the candidate table string
# ────────────────────────────────────────────────────────────────────────────


def _format_candidates(candidates: list[dict]) -> str:
    """Format a list of scored candidate dicts into a readable markdown table.

    Args:
        candidates: Each dict should contain at least ``ticker`` and ``score``
            keys plus any fundamentals returned by the engine.

    Returns:
        A markdown-formatted table string.
    """
    if not candidates:
        return "_No candidates available._"

    # Collect all keys across candidates for column headers
    all_keys: list[str] = []
    for c in candidates:
        for k in c:
            if k not in all_keys:
                all_keys.append(k)

    # Header row
    header = "| " + " | ".join(all_keys) + " |"
    separator = "| " + " | ".join("---" for _ in all_keys) + " |"
    rows = []
    for c in candidates:
        row = "| " + " | ".join(str(c.get(k, "")) for k in all_keys) + " |"
        rows.append(row)
    return "\n".join([header, separator, *rows])


def _format_rejection_log(rejection_log: list[dict]) -> str:
    """Build a human-readable rejection history string.

    Args:
        rejection_log: List of ``{"long": …, "short": …, "reason": …}`` dicts.

    Returns:
        A numbered list of previously rejected pairs with reasons.
    """
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


def screener_node(state: HedgeBuilderState) -> dict:
    """Screen sector constituents and select a long/short pair.

    This function is registered as a **LangGraph node**.  It:

    1. Fetches the sector universe and fundamentals from ``engine``.
    2. Scores each ticker deterministically with ``engine.verifier``.
    3. Asks the LLM to pick the best long/short pair (excluding rejects).
    4. Returns the selection into the graph state.

    On retry iterations (``attempt_count > 0``), previously rejected pairs
    are shown to the LLM so it avoids re-proposing them.

    Args:
        state: Current graph state containing ``target_sector``, ``thesis``,
            ``attempt_count``, and ``rejection_log``.

    Returns:
        Partial state dict updating ``sector_tickers``, ``long_candidates``,
        ``short_candidates``, ``selected_long``, ``selected_short``, and
        appending an assistant message with reasoning.
    """
    sector = state.target_sector
    thesis = state.thesis
    attempt = state.attempt_count
    rejection_log = state.rejection_log

    logger.info(
        "Screener ▸ Attempt %d | Sector: %s | Rejected pairs so far: %d",
        attempt + 1,
        sector,
        len(rejection_log),
    )

    # ── 1. Get sector universe ─────────────────────────────────────────
    try:
        from engine.data_fetcher import get_sector_constituents, get_fundamentals

        sector_tickers: list[str] = get_sector_constituents(sector)
        logger.info("Screener ▸ Fetched %d tickers for %s", len(sector_tickers), sector)
    except Exception as exc:
        logger.error("Screener ▸ Failed to fetch sector constituents: %s", exc)
        sector_tickers = []

    # ── 2. Fetch fundamentals and score ────────────────────────────────
    all_candidates: list[dict] = []
    try:
        from engine.verifier import score_candidate

        for ticker in sector_tickers:
            try:
                fundamentals: dict = get_fundamentals(ticker)
                score: float = score_candidate(ticker, fundamentals)
                candidate = {"ticker": ticker, "score": score, **fundamentals}
                all_candidates.append(candidate)
            except Exception as exc:
                logger.warning("Screener ▸ Skipping %s: %s", ticker, exc)
                continue
    except Exception as exc:
        logger.error("Screener ▸ Scoring pipeline error: %s", exc)

    # ── 3. Separate into long (high score) and short (low score) ───────
    sorted_candidates = sorted(all_candidates, key=lambda c: c.get("score", 0), reverse=True)
    long_candidates = sorted_candidates[: max(len(sorted_candidates) // 2, 1)]
    short_candidates = sorted_candidates[max(len(sorted_candidates) // 2, 1) :]

    # ── 4. Build excluded pairs set for the LLM ───────────────────────
    excluded_pairs = {
        (entry["long"], entry["short"])
        for entry in rejection_log
        if "long" in entry and "short" in entry
    }

    # ── 5. Ask LLM to select the pair ─────────────────────────────────
    user_content = (
        f"## Thesis\n{thesis}\n\n"
        f"## Attempt\n{attempt + 1} of {state.max_attempts}\n\n"
        f"## Long Candidates (sorted best→worst)\n"
        f"{_format_candidates(long_candidates)}\n\n"
        f"## Short Candidates (sorted worst→best)\n"
        f"{_format_candidates(short_candidates)}\n\n"
        f"## Previously Rejected Pairs (DO NOT re-select these)\n"
        f"{_format_rejection_log(rejection_log)}\n"
    )

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
        )
        structured_llm = llm.with_structured_output(PairSelection)

        selection: PairSelection = structured_llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ]
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

    # ── 6. Build partial state update ──────────────────────────────────
    summary_msg = (
        f"**Screener – Attempt {attempt + 1}**\n\n"
        f"- **Long:** {selected_long}\n"
        f"- **Short:** {selected_short}\n\n"
        f"**Reasoning:** {reasoning}"
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

    This is a purely deterministic fallback used when the LLM is unavailable
    or accidentally re-proposes a rejected pair.

    Args:
        long_candidates: Descending-score sorted list of candidate dicts.
        short_candidates: Ascending-score sorted list of candidate dicts.
        excluded: Set of ``(long_ticker, short_ticker)`` tuples to skip.

    Returns:
        Tuple of ``(selected_long, selected_short, reasoning)``.
    """
    for lc in long_candidates:
        for sc in short_candidates:
            lt = lc.get("ticker", "")
            st = sc.get("ticker", "")
            if lt and st and (lt, st) not in excluded:
                return (
                    lt,
                    st,
                    "Deterministic fallback: highest-scored long vs lowest-scored short "
                    "that has not been previously rejected.",
                )

    # Absolute last resort – return whatever we have
    lt = long_candidates[0]["ticker"] if long_candidates else ""
    st = short_candidates[0]["ticker"] if short_candidates else ""
    return lt, st, "Absolute fallback – no non-rejected pairs available."
