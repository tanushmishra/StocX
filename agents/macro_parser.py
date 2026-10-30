"""Macro Intent Parser – LLM node that extracts structured trading parameters.

This agent takes a free-form thesis string (e.g. *"Bullish on Indian IT,
terrified of a US recession crash"*) and uses **Gemini 2.5 Flash** with
Pydantic structured output to resolve it into concrete parameters the
downstream quant pipeline can consume.

The LLM is instructed to act as a *macro strategist* and map natural language
to:

* ``target_sector`` – an NSE sector index name.
* ``benchmark`` – the benchmark index to compute beta against.
* ``lookback_days`` – trailing window length.
* ``stress_regime`` – a named historical drawdown window.

If the LLM fails or returns an incomplete response, sensible defaults are
applied so the pipeline never crashes at this stage.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from agents.gemini_client import get_gemini_client, invoke_with_retry
from pydantic import BaseModel, Field

from agents.state import HedgeBuilderState, StateProxy, wrap_state

logger = logging.getLogger(__name__)


def _get(state: Any, key: str, default: Any = None) -> Any:
    """Safely get an attribute or dictionary key from state."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)

# ────────────────────────────────────────────────────────────────────────────
# Structured output schema for the LLM
# ────────────────────────────────────────────────────────────────────────────

class MacroIntent(BaseModel):
    """Pydantic model that the LLM must populate via structured output.

    Attributes:
        target_sector: NSE sector index name (e.g. ``"NIFTY IT"``).
        benchmark: Benchmark index ticker for beta calculation.
        lookback_days: Number of trailing calendar days for price data.
        stress_regime: Named stress-test window identifier.
        reasoning: One-paragraph explanation of *why* these parameters
            were chosen, grounding the decision in the thesis.
    """

    target_sector: str = Field(
        description=(
            "NSE sector index name that best matches the thesis. "
            "Examples: NIFTY IT, NIFTY BANK, NIFTY PHARMA, NIFTY AUTO, "
            "NIFTY FMCG, NIFTY METAL, NIFTY ENERGY, NIFTY REALTY, "
            "NIFTY INFRA, NIFTY PSE, NIFTY MEDIA."
        ),
    )
    benchmark: str = Field(
        default="^NSEI",
        description=(
            "Yahoo Finance ticker for the benchmark index. "
            "Defaults to ^NSEI (Nifty 50).  Use ^NSEBANK for bank-heavy "
            "theses or ^BSESN for broader BSE coverage."
        ),
    )
    lookback_days: int = Field(
        default=252,
        description=(
            "Number of trailing calendar days of price history to fetch. "
            "252 ≈ 1 trading year.  Use 504 for longer-horizon theses."
        ),
    )
    stress_regime: str = Field(
        default="COVID_2020",
        description=(
            "Named historical stress period to simulate. "
            "Options: COVID_2020, TAPER_TANTRUM_2013, DEMONETISATION_2016, "
            "IL&FS_2018, GFC_2008, RUSSIA_UKRAINE_2022."
        ),
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of the mapping from thesis to parameters.",
    )


# ────────────────────────────────────────────────────────────────────────────
# System prompt
# ────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are **MacroStrategyGPT**, an expert Indian equity macro strategist.

Given a portfolio manager's free-form thesis, extract the structured trading
parameters listed in the output schema.

Rules:
1. ``target_sector`` MUST be a valid NSE sector index name (e.g. "NIFTY IT").
2. Choose the ``benchmark`` that is most economically relevant to the thesis.
3. If the thesis implies long-horizon conviction, set ``lookback_days`` to 504;
   otherwise default to 252.
4. Pick the ``stress_regime`` whose macro drivers are most similar to the risk
   the PM is worried about.
5. Provide a brief ``reasoning`` paragraph grounding every choice in the thesis.

If any field is ambiguous, prefer the conservative default.
"""

# ────────────────────────────────────────────────────────────────────────────
# Fallback defaults
# ────────────────────────────────────────────────────────────────────────────

def _resolve_fallback_intent(thesis: str) -> MacroIntent:
    """Heuristic fallback to extract sector and stress regime when LLM is unavailable."""
    t = (thesis or "").lower()
    sector = "NIFTY IT"
    if any(w in t for w in ["bank", "finan", "credit", "lending", "hdfc", "icici", "kotak", "sbi", "axis"]):
        sector = "NIFTY BANK"
    elif any(w in t for w in ["auto", "car", "motor", "vehicle", "maruti", "tata motor", "eicher", "tvs"]):
        sector = "NIFTY AUTO"
    elif any(w in t for w in ["pharma", "drug", "health", "biotech", "sunpharma", "cipla", "drreddy"]):
        sector = "NIFTY PHARMA"
    elif any(w in t for w in ["fmcg", "consumer", "itc", "hul", "nestle"]):
        sector = "NIFTY FMCG"
    elif any(w in t for w in ["metal", "steel", "tata steel", "jsw"]):
        sector = "NIFTY METAL"

    lookback = 504 if any(w in t for w in ["2y", "two year", "long-term", "long term", "504"]) else 252

    stress = "COVID_2020"
    if any(w in t for w in ["2008", "gfc", "lehman", "financial crisis"]):
        stress = "2008_GFC"
    elif any(w in t for w in ["tech", "selloff", "2022"]):
        stress = "TECH_SELLOFF_2022"
    elif any(w in t for w in ["election", "2024", "poll"]):
        stress = "ELECTION_2024"

    return MacroIntent(
        target_sector=sector,
        benchmark="^NSEI",
        lookback_days=lookback,
        stress_regime=stress,
        reasoning=f"Keyword heuristic fallback resolved sector to '{sector}', benchmark '^NSEI', and stress '{stress}'.",
    )

_FALLBACK_INTENT = _resolve_fallback_intent("")

# ────────────────────────────────────────────────────────────────────────────
# Node function
# ────────────────────────────────────────────────────────────────────────────


def macro_parser_node(state: HedgeBuilderState | dict[str, Any]) -> dict:
    """Parse a natural-language thesis into structured macro parameters.

    This function is registered as a **LangGraph node**.  It:

    1. Instantiates a ``ChatGoogleGenerativeAI`` with structured output.
    2. Sends the thesis through with a macro-strategist system prompt.
    3. Merges the extracted parameters back into the graph state.

    Args:
        state: The current graph state.  Must contain a non-empty ``thesis``.

    Returns:
        A partial state dict with ``target_sector``, ``benchmark``,
        ``lookback_days``, ``stress_regime``, and an appended assistant
        message summarising the extraction.
    """
    state = wrap_state(state)
    thesis = state.thesis or state.get("thesis", "")
    logger.info("MacroParser ▸ Parsing thesis: %s", thesis[:120])

    try:
        # ── Invoke LLM with structured output ──────────────────────────
        structured_llm = get_gemini_client(
            model_type="fast",
            temperature=0.2,
            structured_schema=MacroIntent,
        )

        result: MacroIntent = invoke_with_retry(
            structured_llm,
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=f"Thesis: {thesis}"),
            ],
        )
        logger.info(
            "MacroParser ▸ Extracted sector=%s benchmark=%s lookback=%d stress=%s",
            result.target_sector,
            result.benchmark,
            result.lookback_days,
            result.stress_regime,
        )

    except Exception as exc:
        # Graceful degradation: log the error and use fallback defaults
        logger.error("MacroParser ▸ LLM call failed (%s). Using heuristic fallback defaults.", exc)
        result = _resolve_fallback_intent(thesis)

    # ── Preserve explicit configuration from state / sidebar if provided ──
    user_lookback = getattr(state, "lookback_days", None) or state.get("lookback_days")
    final_lookback = int(user_lookback) if user_lookback else result.lookback_days

    user_benchmark = getattr(state, "benchmark", None) or state.get("benchmark")
    final_benchmark = user_benchmark if user_benchmark else result.benchmark

    user_stress = getattr(state, "stress_regime", None) or state.get("stress_regime")
    final_stress = user_stress if user_stress else result.stress_regime

    # ── Build the partial state update ─────────────────────────────────
    summary_msg = (
        f"**Macro Intent Parsed**\n\n"
        f"- **Sector:** {result.target_sector}\n"
        f"- **Benchmark:** {final_benchmark}\n"
        f"- **Lookback:** {final_lookback} days\n"
        f"- **Stress regime:** {final_stress}\n\n"
        f"**Reasoning:** {result.reasoning}"
    )

    return {
        "target_sector": result.target_sector,
        "benchmark": final_benchmark,
        "lookback_days": final_lookback,
        "stress_regime": final_stress,
        "messages": [{"role": "assistant", "content": summary_msg}],
    }
