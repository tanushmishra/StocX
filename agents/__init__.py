"""Market-Neutral Hedge Builder – LangGraph Multi-Agent Orchestration System.

This package implements a cyclical multi-agent graph that:

1. **Macro Parser** – Extracts structured trading intent from natural language.
2. **Screener** – Identifies long/short pair candidates via fundamentals.
3. **Quant Engine** – Runs deterministic beta, cointegration, and backtest math.
4. **Risk Verifier** – Adversarially gates pairs; triggers a self-correction loop
   back to the Screener when a pair is rejected.
5. **CRO Reporter** – Produces an institutional-grade executive memo.

Architecture invariant
----------------------
LLM agents **read** numbers computed by the deterministic ``engine`` package but
**never** compute them.  All quantitative work flows through ``engine.*``
functions so that results are reproducible and auditable.
"""

from agents.graph import build_graph, run_hedge_builder
from agents.state import HedgeBuilderState, StateProxy, wrap_state

__all__ = [
    "build_graph",
    "run_hedge_builder",
    "HedgeBuilderState",
    "StateProxy",
    "wrap_state",
]
