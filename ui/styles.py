"""
Custom CSS styles for the Market-Neutral Hedge Builder dashboard.

Provides a warm beige / editorial fintech theme with soft cream cards,
warm sand borders, high-contrast typography, consistent color coding
(dark green = hedged/positive, crimson = unhedged/negative),
and responsive grid layout.
"""

MAIN_CSS = """
<style>
/* ── Import Google Fonts ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root Variables (Beige Fintech Theme) ────────────────────────── */
:root {
    --bg-primary:    #f7f4eb;
    --bg-secondary:  #efe9dc;
    --bg-card:       #ffffff;
    --bg-card-hover: #faf7f0;
    --border-glass:  rgba(168, 148, 120, 0.32);
    --border-warm:   #dcd2be;
    --text-primary:  #2b2625;
    --text-secondary:#5c544e;
    --text-muted:    #7e746c;
    --green:         #15803d;
    --green-dim:     rgba(21, 128, 61, 0.12);
    --red:           #b91c1c;
    --red-dim:       rgba(185, 28, 28, 0.10);
    --blue:          #1d4ed8;
    --blue-dim:      rgba(29, 78, 216, 0.12);
    --amber:         #b45309;
    --amber-dim:     rgba(180, 83, 9, 0.12);
    --purple:        #7e22ce;
    --cyan:          #0e7490;
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
    background: linear-gradient(180deg, #ede7d8 0%, #e2dac7 100%) !important;
    border-right: 1px solid var(--border-warm) !important;
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
    background: linear-gradient(135deg, rgba(235, 225, 205, 0.7) 0%, rgba(220, 205, 180, 0.7) 100%);
    border-radius: var(--radius);
    border: 1px solid var(--border-warm);
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 10px rgba(100, 80, 60, 0.05);
}
.hero-header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #78350f, #92400e, #451a03);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
}
.hero-header p {
    color: var(--text-secondary);
    font-size: 0.95rem;
    letter-spacing: 0.5px;
    font-weight: 500;
}

/* ── Glass / Card Metric ─────────────────────────────────────────── */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border-warm);
    border-radius: var(--radius);
    padding: 1.25rem 1.35rem;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 6px rgba(100, 80, 60, 0.05);
}
.metric-card:hover {
    background: var(--bg-card-hover);
    border-color: rgba(140, 110, 80, 0.45);
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(100, 80, 60, 0.10);
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
    opacity: 0.85;
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
    border-bottom: 1px solid var(--border-warm);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ── Agent Trace Panel ───────────────────────────────────────────── */
.trace-step {
    padding: 0.65rem 1rem;
    border-left: 3px solid var(--border-warm);
    margin-bottom: 0.5rem;
    border-radius: 0 8px 8px 0;
    background: #ffffff;
    border-top: 1px solid var(--border-warm);
    border-right: 1px solid var(--border-warm);
    border-bottom: 1px solid var(--border-warm);
    font-size: 0.88rem;
    transition: border-color 0.2s;
}
.trace-step:hover { border-left-color: var(--amber); }
.trace-step .ts-agent {
    font-weight: 600;
    color: var(--amber);
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
    background: #ffffff;
    border: 1px solid var(--border-warm);
    border-radius: var(--radius);
    padding: 1.5rem 2rem;
    line-height: 1.75;
    box-shadow: 0 2px 6px rgba(100, 80, 60, 0.05);
}
.cro-report h3 {
    color: var(--amber);
    margin-bottom: 0.5rem;
}
.cro-report strong { color: var(--text-primary); }

/* ── F&O Table ───────────────────────────────────────────────────── */
.fno-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border: 1px solid var(--border-warm);
    border-radius: var(--radius);
    overflow: hidden;
    font-size: 0.88rem;
    background: #ffffff;
}
.fno-table thead th {
    background: #ede7d8;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-size: 0.72rem;
    letter-spacing: 1px;
    font-weight: 600;
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border-warm);
}
.fno-table tbody td {
    padding: 0.7rem 1rem;
    border-top: 1px solid var(--border-warm);
    color: var(--text-primary);
}
.fno-table tbody tr:hover {
    background: rgba(180, 130, 80, 0.05);
}

/* ── Plotly chart containers ─────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border-radius: var(--radius);
    border: 1px solid var(--border-warm);
    overflow: hidden;
    background: #ffffff;
}

/* ── Expander styling ────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border-warm) !important;
    border-radius: var(--radius) !important;
    background: #ffffff !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: #b8a995; border-radius: 3px; }

/* ── Button polish ───────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 10px rgba(100,80,60,0.15) !important;
}

/* ── Primary CTA ─────────────────────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #92400e, #78350f) !important;
    color: #fdfbf7 !important;
    border: none !important;
    padding: 0.6rem 2rem !important;
    font-size: 1.05rem !important;
}

/* ── Data table ──────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border-warm) !important;
    overflow: hidden !important;
    background: #ffffff !important;
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
