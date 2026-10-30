"""Market-Neutral Hedge Builder – LangGraph Cyclical StateGraph.

This module defines the full multi-agent orchestration graph:

1. **macro_parser** – Extracts structured intent from natural language.
2. **screener** – Screens candidates and selects the candidate pair.
3. **quant_engine** – Deterministically runs math (Beta, cointegration, backtest).
4. **risk_verifier** – Adversarial gatekeeper.
   - If approved -> routes to **cro_reporter**.
   - If rejected and attempts < max_attempts -> loops back to **screener** (Self-Correction!).
   - If rejected and attempts >= max_attempts -> routes to **cro_reporter** (Exhaustion Report).
5. **cro_reporter** – Produces the executive summary memo.

Architecture Invariant:
----------------------
LLMs never compute numbers; math models never read news. All quant work is
handled strictly in `engine/` and wrapped by `quant_engine_node`.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agents.cro_reporter import cro_reporter_node
from agents.macro_parser import macro_parser_node
from agents.quant_node import quant_engine_node
from agents.risk_verifier import risk_verifier_node
from agents.screener import screener_node
from agents.state import HedgeBuilderState, StateProxy, wrap_state

logger = logging.getLogger(__name__)


def _get(state: Any, key: str, default: Any = None) -> Any:
    """Safely get an attribute or dictionary key from state."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# ────────────────────────────────────────────────────────────────────────────
# Conditional Edge Router
# ────────────────────────────────────────────────────────────────────────────


def should_continue_or_retry(
    state: HedgeBuilderState | dict[str, Any],
) -> Literal["cro_reporter", "screener"]:
    """Conditional router function for the Risk Verifier node.

    Evaluates whether the pair was approved or if another screening iteration
    is required.

    Args:
        state: Current graph state containing `approved`, `attempt_count`,
            and `max_attempts`.

    Returns:
        "cro_reporter" if approved or if retry attempts are exhausted.
        "screener" if rejected and retry attempts remain.
    """
    state = wrap_state(state)
    is_approved = bool(state.approved)
    attempts = int(state.attempt_count)
    max_attempts = int(state.max_attempts)

    if is_approved:
        logger.info(
            "GraphRouter ▸ Pair APPROVED on attempt %d. Routing to CRO Reporter.",
            attempts,
        )
        return "cro_reporter"

    if attempts < max_attempts:
        logger.warning(
            "GraphRouter ▸ Pair REJECTED on attempt %d/%d. Self-correcting: looping back to Screener.",
            attempts,
            max_attempts,
        )
        return "screener"

    logger.error(
        "GraphRouter ▸ Max attempts (%d) exhausted without approval. Routing to CRO Reporter for exit memo.",
        max_attempts,
    )
    return "cro_reporter"


# ────────────────────────────────────────────────────────────────────────────
# Graph Builder
# ────────────────────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Construct and compile the cyclical LangGraph StateGraph.

    Returns:
        A compiled LangGraph instance ready for invocation.
    """
    workflow = StateGraph(HedgeBuilderState)

    # 1. Add all nodes
    workflow.add_node("macro_parser", macro_parser_node)
    workflow.add_node("screener", screener_node)
    workflow.add_node("quant_engine", quant_engine_node)
    workflow.add_node("risk_verifier", risk_verifier_node)
    workflow.add_node("cro_reporter", cro_reporter_node)

    # 2. Add linear deterministic edges
    workflow.add_edge(START, "macro_parser")
    workflow.add_edge("macro_parser", "screener")
    workflow.add_edge("screener", "quant_engine")
    workflow.add_edge("quant_engine", "risk_verifier")

    # 3. Add conditional self-correction edge
    workflow.add_conditional_edges(
        "risk_verifier",
        should_continue_or_retry,
        {
            "screener": "screener",
            "cro_reporter": "cro_reporter",
        },
    )

    # 4. Final edge from CRO reporter to END
    workflow.add_edge("cro_reporter", END)

    return workflow.compile()


# ────────────────────────────────────────────────────────────────────────────
# Top-level Invocation Helper
# ────────────────────────────────────────────────────────────────────────────


def run_hedge_builder(
    thesis: str,
    benchmark: str = "^NSEI",
    lookback_days: int = 252,
    stress_regime: str = "COVID_2020",
    max_attempts: int = 5,
) -> dict[str, Any]:
    """Execute the multi-agent Hedge Builder pipeline from a natural language thesis.

    Args:
        thesis: Natural language market view (e.g., "Bullish on Indian IT, terrified of a crash").
        benchmark: Default benchmark ticker (NSE NIFTY 50 = "^NSEI").
        lookback_days: Trailing window size for historical estimation.
        stress_regime: Identifier for stress testing ("COVID_2020", "2008_GFC", etc.).
        max_attempts: Maximum self-correction iterations.

    Returns:
        Final state dictionary containing pair metrics, weights, CRO report,
        and full verification audit log.
    """
    logger.info("Initializing Hedge Builder run for thesis: '%s'", thesis)
    app = build_graph()

    initial_state = {
        "thesis": thesis,
        "benchmark": benchmark,
        "lookback_days": lookback_days,
        "stress_regime": stress_regime,
        "max_attempts": max_attempts,
        "attempt_count": 0,
        "approved": False,
        "rejection_log": [],
        "messages": [],
    }

    final_state = app.invoke(initial_state)
    logger.info(
        "Hedge Builder completed. Approved: %s, Attempts: %d",
        final_state.get("approved", False),
        final_state.get("attempt_count", 0),
    )
    return final_state
