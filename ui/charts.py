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

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── Palette ──────────────────────────────────────────────────────────────────
_GREEN  = "#15803d"
_RED    = "#b91c1c"
_GREY   = "#78716c"
_BLUE   = "#1d4ed8"
_CYAN   = "#0e7490"
_PURPLE = "#7e22ce"
_AMBER  = "#b45309"

_LAYOUT_COMMON: Dict[str, Any] = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(247, 244, 235, 0.6)",
    font=dict(family="Inter, sans-serif", color="#2b2625"),
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
    for period in crash_periods:
        if not isinstance(period, (tuple, list)) or len(period) < 3:
            continue
        start, end, label = period[0], period[1], period[2]
        fig.add_vrect(
            x0=start,
            x1=end,
            fillcolor="rgba(239,68,68,0.08)",
            layer="below",
            line_width=0,
            annotation_text=str(label),
            annotation_position="top left",
            annotation=dict(font_size=9, font_color=_RED),
        )


def _empty_figure(title_text: str, message: str = "No data available") -> go.Figure:
    """Return an empty dark figure with a descriptive annotation."""
    fig = go.Figure()
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text=title_text, font=dict(size=15)),
        annotations=[
            dict(
                text=message,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color=_GREY),
            )
        ],
    )
    return fig


# ── Public Chart Factories ───────────────────────────────────────────────────

def create_cumulative_returns_figure(
    dates: Sequence,
    nifty_cum: Optional[Sequence[float]] = None,
    unhedged_cum: Optional[Sequence[float]] = None,
    hedged_cum: Optional[Sequence[float]] = None,
    crash_periods: Optional[List[Tuple[str, str, str]]] = None,
) -> go.Figure:
    """Cumulative-returns chart with genuine series and optional crash shading.

    Parameters
    ----------
    dates : array-like
        Date index shared by all series.
    nifty_cum : array-like, optional
        Benchmark return series. Omitted if None. Never invented.
    unhedged_cum, hedged_cum : array-like, optional
        Cumulative return series (1-based, i.e. starting at 1.0).
    crash_periods : list[tuple], optional
        ``(start, end, label)`` tuples rendered as shaded rectangles.

    Returns
    -------
    go.Figure
    """
    if dates is None or len(dates) == 0:
        return _empty_figure("Cumulative Returns", "No date index available")

    if unhedged_cum is None and hedged_cum is None:
        return _empty_figure("Cumulative Returns", "No cumulative return series available")

    fig = go.Figure()

    # NIFTY 50 benchmark (only plotted if genuinely provided)
    if nifty_cum is not None and len(nifty_cum) > 0:
        fig.add_trace(go.Scatter(
            x=dates, y=nifty_cum,
            name="Benchmark",
            line=dict(color=_GREY, dash="dash", width=1.5),
            opacity=0.6,
        ))

    # Unhedged long leg
    if unhedged_cum is not None and len(unhedged_cum) > 0:
        fig.add_trace(go.Scatter(
            x=dates, y=unhedged_cum,
            name="Unhedged Long",
            line=dict(color=_RED, width=2),
        ))

    # Hedged portfolio
    if hedged_cum is not None and len(hedged_cum) > 0:
        fig.add_trace(go.Scatter(
            x=dates, y=hedged_cum,
            name="Hedged Portfolio",
            line=dict(color=_GREEN, width=2.5),
            fill="tonexty" if unhedged_cum is not None else None,
            fillcolor="rgba(34,197,94,0.06)",
        ))

    _add_crash_shading(fig, crash_periods)
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Cumulative Returns (Historical Backtest)", font=dict(size=15)),
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
    if dates is None or rolling_beta is None or len(dates) == 0 or len(rolling_beta) == 0:
        return _empty_figure("Rolling Portfolio Beta", "No rolling beta series available")

    # Filter non-finite or convert safely
    rb = np.asarray(rolling_beta, dtype=float)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=rb,
        name="Rolling β",
        line=dict(color=_BLUE, width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
    ))
    fig.add_hline(
        y=0, line_dash="dot", line_color=_GREY, opacity=0.5,
        annotation_text="β = 0 (Market-Neutral)", annotation_position="bottom right"
    )
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Rolling Portfolio Beta (Historical Estimation)", font=dict(size=15)),
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
    if dates is None or zscore is None or len(dates) == 0 or len(zscore) == 0:
        return _empty_figure("Spread Z-Score", "No spread Z-score data available")

    zs = np.asarray(zscore, dtype=float)
    finite_zs = zs[np.isfinite(zs)]
    max_bound = max(4.0, float(np.max(finite_zs)) + 0.5) if len(finite_zs) > 0 else 4.0
    min_bound = min(-4.0, float(np.min(finite_zs)) - 0.5) if len(finite_zs) > 0 else -4.0

    fig = go.Figure()
    # Band shading
    fig.add_hrect(
        y0=lower_band, y1=upper_band,
        fillcolor="rgba(34,197,94,0.06)", line_width=0, layer="below"
    )
    fig.add_hrect(
        y0=upper_band, y1=max_bound,
        fillcolor="rgba(239,68,68,0.06)", line_width=0, layer="below"
    )
    fig.add_hrect(
        y0=min_bound, y1=lower_band,
        fillcolor="rgba(239,68,68,0.06)", line_width=0, layer="below"
    )
    # Z-score line
    fig.add_trace(go.Scatter(
        x=dates, y=zs,
        name="Z-Score",
        line=dict(color=_CYAN, width=2),
    ))
    # Threshold lines
    for band, label in [(upper_band, f"+{upper_band}σ"), (lower_band, f"{lower_band}σ")]:
        fig.add_hline(
            y=band, line_dash="dash", line_color=_AMBER, opacity=0.6,
            annotation_text=label, annotation_position="right"
        )
    fig.add_hline(y=0, line_dash="dot", line_color=_GREY, opacity=0.3)

    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Spread Z-Score & Cointegration Bands", font=dict(size=15)),
        yaxis_title="Z-Score",
        height=400,
    )
    return fig


def create_correlation_heatmap_figure(
    corr_matrix: Any,
) -> go.Figure:
    """Correlation matrix heatmap.

    Parameters
    ----------
    corr_matrix : pd.DataFrame or dict
        Square correlation matrix.

    Returns
    -------
    go.Figure
    """
    if corr_matrix is None:
        return _empty_figure("Sector Correlation Matrix", "No correlation data available")

    # If dict, attempt to construct DataFrame
    if isinstance(corr_matrix, dict):
        try:
            corr_matrix = pd.DataFrame(corr_matrix)
        except Exception:
            return _empty_figure("Sector Correlation Matrix", "Invalid correlation matrix format")

    if not isinstance(corr_matrix, pd.DataFrame) or corr_matrix.empty:
        return _empty_figure("Sector Correlation Matrix", "No correlation matrix available")

    labels = list(str(col) for col in corr_matrix.columns)
    z_vals = corr_matrix.values

    fig = go.Figure(data=go.Heatmap(
        z=z_vals,
        x=labels,
        y=labels,
        colorscale=[
            [0.0, "#ef4444"],
            [0.5, "#f7f4eb"],
            [1.0, "#22c55e"],
        ],
        zmin=-1,
        zmax=1,
        text=np.round(z_vals, 2),
        texttemplate="%{text}",
        textfont=dict(size=11),
        hoverongaps=False,
        colorbar=dict(
            title=dict(text="ρ", font=dict(size=12)),
            tickfont=dict(size=10),
            len=0.6,
        ),
    ))
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Sector Correlation Matrix (Historical)", font=dict(size=15)),
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
    if dates is None or unhedged_dd is None or hedged_dd is None or len(dates) == 0:
        return _empty_figure("Drawdown Analysis", "No drawdown series available")

    u_arr = np.asarray(unhedged_dd, dtype=float)
    h_arr = np.asarray(hedged_dd, dtype=float)

    # Scale to percentage if fractional
    u_pct = u_arr * 100 if np.nanmax(np.abs(u_arr)) <= 1.0 else u_arr
    h_pct = h_arr * 100 if np.nanmax(np.abs(h_arr)) <= 1.0 else h_arr

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=u_pct,
        name="Unhedged Drawdown",
        line=dict(color=_RED, width=1.8),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.10)",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=h_pct,
        name="Hedged Drawdown",
        line=dict(color=_GREEN, width=1.8),
        fill="tozeroy",
        fillcolor="rgba(34,197,94,0.08)",
    ))
    fig.update_layout(
        **_LAYOUT_COMMON,
        title=dict(text="Underwater Drawdown (Historical Backtest)", font=dict(size=15)),
        yaxis_title="Drawdown (%)",
        yaxis_ticksuffix="%",
        height=370,
    )
    return fig
