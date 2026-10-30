"""UI package for the Market-Neutral Hedge Builder dashboard."""

from ui.styles import inject_css
from ui.components import (
    render_metric_card,
    render_cumulative_chart,
    render_beta_chart,
    render_zscore_chart,
    render_correlation_heatmap,
    render_drawdown_chart,
    render_agent_trace,
    render_fno_table,
    render_pair_details,
)
from ui.charts import (
    create_cumulative_returns_figure,
    create_rolling_beta_figure,
    create_zscore_figure,
    create_correlation_heatmap_figure,
    create_drawdown_figure,
)

__all__ = [
    "inject_css",
    "render_metric_card",
    "render_cumulative_chart",
    "render_beta_chart",
    "render_zscore_chart",
    "render_correlation_heatmap",
    "render_drawdown_chart",
    "render_agent_trace",
    "render_fno_table",
    "render_pair_details",
    "create_cumulative_returns_figure",
    "create_rolling_beta_figure",
    "create_zscore_figure",
    "create_correlation_heatmap_figure",
    "create_drawdown_figure",
]
