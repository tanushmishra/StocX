"""
Custom CSS styles for the Market-Neutral Hedge Builder dashboard.

Provides a dark professional theme with glass-morphism metric cards,
consistent color coding (green = hedged/positive, red = unhedged/negative),
and responsive grid layout.
"""

MAIN_CSS = """
<style>
/* ── Import Google Fonts ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root Variables ──────────────────────────────────────────────── */
:root {
    --bg-primary:    #0a0e1a;
    --bg-secondary:  #111827;
    --bg-card:       rgba(17, 24, 39, 0.65);
    --bg-card-hover: rgba(30, 41, 59, 0.75);
    --border-glass:  rgba(148, 163, 184, 0.12);
    --text-primary:  #f1f5f9;
    --text-secondary:#94a3b8;
    --text-muted:    #64748b;
    --green:         #22c55e;
    --green-dim:     rgba(34, 197, 94, 0.15);
    --red:           #ef4444;
    --red-dim:       rgba(239, 68, 68, 0.12);
    --blue:          #3b82f6;
    --blue-dim:      rgba(59, 130, 246, 0.15);
    --amber:         #f59e0b;
    --amber-dim:     rgba(245, 158, 11, 0.12);
    --purple:        #a78bfa;
    --cyan:          #22d3ee;
    --radius:        12px;
}

/* ── Global ──────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"] {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"] {
    background-color: transparent !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e1b4b 100%) !important;
    border-right: 1px solid var(--border-glass) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] label {
    color: var(--text-primary) !important;
}

/* ── Hero Header ─────────────────────────────────────────────────── */
.hero-header {
    text-align: center;
    padding: 2rem 1rem 1.5rem;
    background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(167,139,250,0.08) 100%);
    border-radius: var(--radius);
    border: 1px solid var(--border-glass);
    margin-bottom: 1.5rem;
}
.hero-header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #22d3ee);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
}
.hero-header p {
    color: var(--text-secondary);
    font-size: 0.95rem;
    letter-spacing: 0.5px;
}

/* ── Glass Metric Card ───────────────────────────────────────────── */
.metric-card {
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-glass);
    border-radius: var(--radius);
    padding: 1.25rem 1.35rem;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.metric-card:hover {
    background: var(--bg-card-hover);
    border-color: rgba(148, 163, 184, 0.25);
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.35);
}
.metric-card .mc-label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--text-muted);
    margin-bottom: 0.6rem;
}
.metric-card .mc-row {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    margin-bottom: 0.25rem;
}
.metric-card .mc-before {
    font-size: 1.05rem;
    color: var(--red);
    text-decoration: line-through;
    opacity: 0.7;
}
.metric-card .mc-after {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--green);
}
.metric-card .mc-delta {
    font-size: 0.82rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
    display: inline-block;
}
.mc-delta.positive {
    background: var(--green-dim);
    color: var(--green);
}
.mc-delta.negative {
    background: var(--red-dim);
    color: var(--red);
}

/* ── Accent strip on top of card ─────────────────────────────────── */
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: var(--radius) var(--radius) 0 0;
}
.mc-beta::before   { background: linear-gradient(90deg, var(--blue), var(--cyan)); }
.mc-dd::before     { background: linear-gradient(90deg, var(--red), var(--amber)); }
.mc-sharpe::before { background: linear-gradient(90deg, var(--green), var(--cyan)); }
.mc-sortino::before{ background: linear-gradient(90deg, var(--purple), var(--blue)); }

/* ── Section Titles ──────────────────────────────────────────────── */
.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 2rem 0 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border-glass);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ── Agent Trace Panel ───────────────────────────────────────────── */
.trace-step {
    padding: 0.65rem 1rem;
    border-left: 3px solid var(--border-glass);
    margin-bottom: 0.5rem;
    border-radius: 0 8px 8px 0;
    background: rgba(15, 23, 42, 0.5);
    font-size: 0.88rem;
    transition: border-color 0.2s;
}
.trace-step:hover { border-left-color: var(--blue); }
.trace-step .ts-agent {
    font-weight: 600;
    color: var(--cyan);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
}
.trace-step .ts-time {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    float: right;
}
.trace-step.rejected { border-left-color: var(--red); }
.trace-step.approved { border-left-color: var(--green); }

/* ── CRO Report Card ────────────────────────────────────────────── */
.cro-report {
    background: linear-gradient(135deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.8) 100%);
    border: 1px solid var(--border-glass);
    border-radius: var(--radius);
    padding: 1.5rem 2rem;
    line-height: 1.75;
}
.cro-report h3 {
    color: var(--cyan);
    margin-bottom: 0.5rem;
}
.cro-report strong { color: var(--text-primary); }

/* ── F&O Table ───────────────────────────────────────────────────── */
.fno-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border: 1px solid var(--border-glass);
    border-radius: var(--radius);
    overflow: hidden;
    font-size: 0.88rem;
}
.fno-table thead th {
    background: rgba(30, 41, 59, 0.8);
    color: var(--text-secondary);
    text-transform: uppercase;
    font-size: 0.72rem;
    letter-spacing: 1px;
    font-weight: 600;
    padding: 0.75rem 1rem;
    text-align: left;
}
.fno-table tbody td {
    padding: 0.7rem 1rem;
    border-top: 1px solid var(--border-glass);
    color: var(--text-primary);
}
.fno-table tbody tr:hover {
    background: rgba(59,130,246,0.06);
}

/* ── Black Swan Buttons ──────────────────────────────────────────── */
.crash-btn {
    display: block;
    width: 100%;
    padding: 0.55rem 0.8rem;
    margin-bottom: 0.4rem;
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 0.82rem;
    text-align: left;
    transition: all 0.2s;
}
.crash-btn:hover {
    background: rgba(239,68,68,0.18);
    border-color: var(--red);
}

/* ── Plotly chart containers ─────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border-radius: var(--radius);
    border: 1px solid var(--border-glass);
    overflow: hidden;
}

/* ── Expander styling ────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius) !important;
    background: var(--bg-card) !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: var(--text-muted); border-radius: 3px; }

/* ── Button polish ───────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}

/* ── Primary CTA ─────────────────────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
    color: white !important;
    border: none !important;
    padding: 0.6rem 2rem !important;
    font-size: 1.05rem !important;
}

/* ── Data table ──────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border-glass) !important;
    overflow: hidden !important;
}

/* ── Hide Streamlit branding ─────────────────────────────────────── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""


def inject_css() -> None:
    """Inject the full custom CSS into the Streamlit app via st.markdown."""
    import streamlit as st
    st.markdown(MAIN_CSS, unsafe_allow_html=True)
