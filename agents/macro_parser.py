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

from agents.state import HedgeBuilderState

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

_FALLBACK_INTENT = MacroIntent(
    target_sector="NIFTY IT",
    benchmark="^NSEI",
    lookback_days=252,
    stress_regime="COVID_2020",
    reasoning="Fallback defaults applied because the LLM call failed.",
)

# ────────────────────────────────────────────────────────────────────────────
# Node function
# ────────────────────────────────────────────────────────────────────────────


def macro_parser_node(state: HedgeBuilderState) -> dict:
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
    thesis = _get(state, "thesis", "")
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
        logger.error("MacroParser ▸ LLM call failed (%s). Using fallback defaults.", exc)
        result = _FALLBACK_INTENT

    # ── Build the partial state update ─────────────────────────────────
    summary_msg = (
        f"**Macro Intent Parsed**\n\n"
        f"- **Sector:** {result.target_sector}\n"
        f"- **Benchmark:** {result.benchmark}\n"
        f"- **Lookback:** {result.lookback_days} days\n"
        f"- **Stress regime:** {result.stress_regime}\n\n"
        f"**Reasoning:** {result.reasoning}"
    )

    return {
        "target_sector": result.target_sector,
        "benchmark": result.benchmark,
        "lookback_days": result.lookback_days,
        "stress_regime": result.stress_regime,
        "messages": [{"role": "assistant", "content": summary_msg}],
    }
