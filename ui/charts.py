"""
Plotly chart factory functions for the Market-Neutral Hedge Builder dashboard.

All functions return a ``plotly.graph_objects.Figure`` configured with the
``plotly_dark`` template and a consistent colour palette so the caller can
simply pass the figure to ``st.plotly_chart``.

Colour conventions
------------------
* **NIFTY 50 benchmark** – grey dashed
* **Unhedged long book** – red (#ef4444)
* **Hedged portfolio**   – green (#22c55e)
* **Crash regimes**      – translucent red rectangles
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── Palette ──────────────────────────────────────────────────────────────────
_GREEN  = "#22c55e"
_RED    = "#ef4444"
_GREY   = "#94a3b8"
_BLUE   = "#3b82f6"
_CYAN   = "#22d3ee"
_PURPLE = "#a78bfa"
_AMBER  = "#f59e0b"

_LAYOUT_COMMON: Dict[str, Any] = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(10,14,26,0.6)",
    font=dict(family="Inter, sans-serif", color="#f1f5f9"),
    margin=dict(l=50, r=20, t=45, b=40),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11),
    ),
    hovermode="x unified",
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _add_crash_shading(
    fig: go.Figure,
    crash_periods: Optional[List[Tuple[str, str, str]]] = None,
) -> None:
    """Add translucent red rectangles for crash regimes.

    Parameters
    ----------
    crash_periods:
        List of ``(start_date, end_date, label)`` tuples.
    """
    if not crash_periods:
        return
    for start, end, label in crash_periods:
        fig.add_vrect(
            x0=start,
            x1=end,
            fillcolor="rgba(239,68,68,0.08)",
            layer="below",
            line_width=0,
            annotation_text=label,
            annotation_position="top left",
            annotation=dict(font_size=9, font_color=_RED),
        )


# ── Public Chart Factories ───────────────────────────────────────────────────

def create_cumulative_returns_figure(
    dates: Sequence,
    nifty_cum: Sequence[float],
    unhedged_cum: Sequence[float],
    hedged_cum: Sequence[float],
    crash_periods: Optional[List[Tuple[str, str, str]]] = None,
) -> go.Figure:
    """Cumulative-returns chart with three series and optional crash shading.

    Parameters
    ----------
    dates : array-like
        Date index shared by all series.
    nifty_cum, unhedged_cum, hedged_cum : array-like
        Cumulative return series (1-based, i.e. starting at 1.0).
    crash_periods : list[tuple], optional
        ``(start, end, label)`` tuples rendered as shaded rectangles.

    Returns
    -------
    go.Figure
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=nifty_cum,
        name="NIFTY 50",
        line=dict(color=_GREY, dash="dash", width=1.5),
        opacity=0.6,
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=unhedged_cum,
        name="Unhedged Long",
        line=dict(color=_RED, width=2),
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=hedged_cum,
        name="Hedged Portfolio",
        line=dict(color=_GREEN, width=2.5),
        fill="tonexty",
        fillcolor="rgba(34,197,94,0.06)",
    ))
    _add_crash_shading(fig, crash_periods)
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Cumulative Returns", font=dict(size=15)),
        yaxis_title="Growth of ₹1",
        xaxis_title=None,
        yaxis_tickformat=".2f",
        height=400,
    )
    return fig


def create_rolling_beta_figure(
    dates: Sequence,
    rolling_beta: Sequence[float],
) -> go.Figure:
    """Rolling portfolio beta with a zero-line reference.

    Parameters
    ----------
    dates : array-like
    rolling_beta : array-like

    Returns
    -------
    go.Figure
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=rolling_beta,
        name="Rolling β",
        line=dict(color=_BLUE, width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=_GREY, opacity=0.5,
                  annotation_text="β = 0", annotation_position="bottom right")
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Rolling Portfolio Beta", font=dict(size=15)),
        yaxis_title="Beta",
        height=400,
    )
    return fig


def create_zscore_figure(
    dates: Sequence,
    zscore: Sequence[float],
    upper_band: float = 1.5,
    lower_band: float = -1.5,
) -> go.Figure:
    """Spread Z-score with ±σ entry-signal bands.

    Parameters
    ----------
    dates : array-like
    zscore : array-like
    upper_band, lower_band : float
        Threshold lines for entry signals (default ±1.5).

    Returns
    -------
    go.Figure
    """
    zs = np.asarray(zscore, dtype=float)
    colors = np.where(np.abs(zs) >= upper_band, _AMBER, _CYAN)

    fig = go.Figure()
    # Band shading
    fig.add_hrect(y0=lower_band, y1=upper_band,
                  fillcolor="rgba(34,197,94,0.06)", line_width=0, layer="below")
    fig.add_hrect(y0=upper_band, y1=max(4, float(np.nanmax(zs)) + 0.5),
                  fillcolor="rgba(239,68,68,0.06)", line_width=0, layer="below")
    fig.add_hrect(y0=min(-4, float(np.nanmin(zs)) - 0.5), y1=lower_band,
                  fillcolor="rgba(239,68,68,0.06)", line_width=0, layer="below")
    # Z-score line
    fig.add_trace(go.Scatter(
        x=dates, y=zs,
        name="Z-Score",
        line=dict(color=_CYAN, width=2),
    ))
    # Threshold lines
    for band, label in [(upper_band, f"+{upper_band}σ"), (lower_band, f"{lower_band}σ")]:
        fig.add_hline(y=band, line_dash="dash", line_color=_AMBER, opacity=0.6,
                      annotation_text=label, annotation_position="right")
    fig.add_hline(y=0, line_dash="dot", line_color=_GREY, opacity=0.3)

    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Spread Z-Score", font=dict(size=15)),
        yaxis_title="Z-Score",
        height=400,
    )
    return fig


def create_correlation_heatmap_figure(
    corr_matrix: pd.DataFrame,
) -> go.Figure:
    """Correlation matrix heatmap.

    Parameters
    ----------
    corr_matrix : pd.DataFrame
        Square correlation matrix.

    Returns
    -------
    go.Figure
    """
    labels = list(corr_matrix.columns)
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=labels,
        y=labels,
        colorscale=[
            [0.0, "#ef4444"],
            [0.5, "#1e293b"],
            [1.0, "#22c55e"],
        ],
        zmin=-1,
        zmax=1,
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=11),
        hoverongaps=False,
        colorbar=dict(
            title="ρ",
            titlefont=dict(size=12),
            tickfont=dict(size=10),
            len=0.6,
        ),
    ))
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Sector Correlation Matrix", font=dict(size=15)),
        height=420,
        xaxis=dict(tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
    )
    return fig


def create_drawdown_figure(
    dates: Sequence,
    unhedged_dd: Sequence[float],
    hedged_dd: Sequence[float],
) -> go.Figure:
    """Drawdown chart comparing unhedged vs hedged underwater curves.

    Parameters
    ----------
    dates : array-like
    unhedged_dd, hedged_dd : array-like
        Drawdown series (negative values, e.g. -0.15 for -15 %).

    Returns
    -------
    go.Figure
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=np.asarray(unhedged_dd) * 100,
        name="Unhedged DD",
        line=dict(color=_RED, width=1.8),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.10)",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=np.asarray(hedged_dd) * 100,
        name="Hedged DD",
        line=dict(color=_GREEN, width=1.8),
        fill="tozeroy",
        fillcolor="rgba(34,197,94,0.08)",
    ))
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Drawdown", font=dict(size=15)),
        yaxis_title="Drawdown (%)",
        yaxis_ticksuffix="%",
        height=370,
    )
    return fig
