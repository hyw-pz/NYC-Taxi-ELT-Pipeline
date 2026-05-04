"""
NYC Taxi Analytics Dashboard
Reads local parquet files from the NYC TLC dataset.
Usage: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import glob

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NYC Taxi Analytics",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    .main { background-color: #0f0f0f; }
    .block-container { padding-top: 2rem; }

    /* KPI cards */
    .kpi-card {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    .kpi-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #666;
        margin-bottom: 0.3rem;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 600;
        color: #f5f5f5;
        line-height: 1.1;
    }
    .kpi-delta {
        font-family: 'DM Mono', monospace;
        font-size: 0.75rem;
        color: #f5c518;
        margin-top: 0.2rem;
    }

    h1, h2, h3 { font-family: 'DM Sans', sans-serif !important; }
    .section-title {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #f5c518;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Color palette ─────────────────────────────────────────────────────────────
YELLOW   = "#f5c518"
DARK_BG  = "#0f0f0f"
CARD_BG  = "#1a1a1a"
GRID     = "#2a2a2a"
TEXT     = "#f5f5f5"
MUTED    = "#888888"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans, sans-serif", color=TEXT),
    xaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(size=11)),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(size=11)),
    margin=dict(l=0, r=0, t=30, b=0),
)

# ── Data loading ──────────────────────────────────────────────────────────────
PAYMENT_MAP = {1: "Credit Card", 2: "Cash", 3: "No Charge", 4: "Dispute", 5: "Unknown"}

@st.cache_data(show_spinner=False)
def load_data(paths: list[str]) -> pd.DataFrame:
    dfs = []
    for p in paths:
        df = pd.read_parquet(p, columns=[
            "tpep_pickup_datetime", "tpep_dropoff_datetime",
            "passenger_count", "trip_distance",
            "fare_amount", "tip_amount", "total_amount",
            "payment_type", "PULocationID", "DOLocationID",
        ])
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True)

    # Basic cleaning — mirrors the WHERE clauses in the SQL views
    df = df[
        df["fare_amount"].between(2.5, 500) &
        df["trip_distance"].between(0.01, 100) &
        df["tpep_pickup_datetime"].notna()
    ].copy()

    df["pickup_hour"]  = df["tpep_pickup_datetime"].dt.hour
    df["trip_date"]    = df["tpep_pickup_datetime"].dt.date
    df["trip_minutes"] = (
        (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"])
        .dt.total_seconds() / 60
    ).clip(1, 180)
    df["fare_per_mile"] = (df["fare_amount"] / df["trip_distance"]).clip(0, 50)
    df["tip_pct"]       = (df["tip_amount"] / df["fare_amount"] * 100).clip(0, 100)
    df["payment_label"] = df["payment_type"].map(PAYMENT_MAP).fillna("Unknown")

    def dist_bucket(d):
        if d < 1:   return "< 1 mi"
        if d < 3:   return "1–3 mi"
        if d < 10:  return "3–10 mi"
        return "10+ mi"
    df["dist_bucket"] = df["trip_distance"].apply(dist_bucket)

    return df

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚕 NYC Taxi")
    st.markdown("---")

    # File discovery
    default_glob = os.path.join(os.path.dirname(__file__), "*.parquet")
    found = sorted(glob.glob(default_glob))

    st.markdown("**Data files**")
    uploaded = st.file_uploader(
        "Upload parquet file(s)", type="parquet",
        accept_multiple_files=True, label_visibility="collapsed"
    )

    if uploaded:
        import tempfile, pathlib
        tmp_dir = tempfile.mkdtemp()
        paths = []
        for f in uploaded:
            p = pathlib.Path(tmp_dir) / f.name
            p.write_bytes(f.read())
            paths.append(str(p))
    elif found:
        paths = found
        st.caption(f"Auto-detected {len(found)} file(s) in project folder.")
    else:
        st.warning("No parquet files found. Upload a file above.")
        st.stop()

    with st.spinner("Loading data…"):
        df = load_data(paths)

    st.markdown("---")
    st.markdown(f"**{len(df):,}** trips loaded")

    st.markdown("**Filters**")
    hour_range = st.slider("Pickup hour", 0, 23, (0, 23))
    dist_opts  = st.multiselect(
        "Distance bucket",
        ["< 1 mi", "1–3 mi", "3–10 mi", "10+ mi"],
        default=["< 1 mi", "1–3 mi", "3–10 mi", "10+ mi"],
    )
    pay_opts = st.multiselect(
        "Payment type",
        df["payment_label"].unique().tolist(),
        default=df["payment_label"].unique().tolist(),
    )

    # Apply filters
    mask = (
        df["pickup_hour"].between(*hour_range) &
        df["dist_bucket"].isin(dist_opts) &
        df["payment_label"].isin(pay_opts)
    )
    dff = df[mask]

    st.markdown("---")
    st.caption("Data: NYC TLC · Pipeline: Airflow + Snowflake")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# NYC Yellow Taxi — Analytics Dashboard")
st.markdown(
    f"<span style='color:{MUTED};font-size:0.85rem'>"
    f"Showing <b style='color:{TEXT}'>{len(dff):,}</b> trips after filters"
    f"</span>", unsafe_allow_html=True
)
st.markdown("---")

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

def kpi(col, label, value, delta=None):
    delta_html = f"<div class='kpi-delta'>{delta}</div>" if delta else ""
    col.markdown(
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"{delta_html}</div>",
        unsafe_allow_html=True,
    )

total_rev   = dff["total_amount"].sum()
avg_fare    = dff["fare_amount"].mean()
avg_dist    = dff["trip_distance"].mean()
avg_tip_pct = dff["tip_pct"].mean()
cc_pct      = (dff["payment_label"] == "Credit Card").mean() * 100

kpi(k1, "Total Revenue",   f"${total_rev/1e6:.1f}M")
kpi(k2, "Avg Fare",        f"${avg_fare:.2f}")
kpi(k3, "Avg Distance",    f"{avg_dist:.1f} mi")
kpi(k4, "Avg Tip",         f"{avg_tip_pct:.1f}%")
kpi(k5, "Credit Card %",   f"{cc_pct:.1f}%")

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 1: Revenue trend + Hourly pattern ─────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown("<div class='section-title'>Daily Revenue</div>", unsafe_allow_html=True)
    daily = (
        dff.groupby("trip_date")
        .agg(revenue=("total_amount", "sum"), trips=("fare_amount", "count"))
        .reset_index()
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["trip_date"], y=daily["revenue"],
        mode="lines", fill="tozeroy",
        line=dict(color=YELLOW, width=2),
        fillcolor="rgba(245,197,24,0.08)",
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, height=260)
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown("<div class='section-title'>Trips by Hour</div>", unsafe_allow_html=True)
    hourly = dff.groupby("pickup_hour").size().reset_index(name="trips")
    fig2 = px.bar(
        hourly, x="pickup_hour", y="trips",
        color_discrete_sequence=[YELLOW],
    )
    fig2.update_traces(marker_line_width=0)
    fig2.update_layout(**PLOTLY_LAYOUT, height=260, bargap=0.15)
    fig2.update_xaxes(tickvals=list(range(0, 24, 3)),
                      ticktext=[f"{h:02d}:00" for h in range(0, 24, 3)])
    st.plotly_chart(fig2, use_container_width=True)

# ── Row 2: Payment breakdown + Fare by distance ───────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("<div class='section-title'>Payment Method</div>", unsafe_allow_html=True)
    pay = (
        dff.groupby("payment_label")
        .agg(trips=("fare_amount", "count"), avg_tip=("tip_amount", "mean"))
        .reset_index()
        .sort_values("trips", ascending=False)
    )
    fig3 = px.bar(
        pay, x="payment_label", y="trips",
        color="payment_label",
        color_discrete_sequence=[YELLOW, "#888", "#555", "#333", "#222"],
        hover_data={"avg_tip": ":.2f"},
    )
    fig3.update_traces(marker_line_width=0)
    fig3.update_layout(**PLOTLY_LAYOUT, height=280, showlegend=False)
    fig3.update_yaxes(tickformat=",")
    st.plotly_chart(fig3, use_container_width=True)

with col_b:
    st.markdown("<div class='section-title'>Fare vs Distance Bucket</div>", unsafe_allow_html=True)
    bucket_order = ["< 1 mi", "1–3 mi", "3–10 mi", "10+ mi"]
    dist_agg = (
        dff.groupby("dist_bucket")
        .agg(avg_fare=("fare_amount", "mean"), avg_tip=("tip_amount", "mean"),
             fare_per_mile=("fare_per_mile", "mean"))
        .reindex(bucket_order).reset_index()
    )
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        name="Avg Fare", x=dist_agg["dist_bucket"], y=dist_agg["avg_fare"],
        marker_color=YELLOW, marker_line_width=0,
    ))
    fig4.add_trace(go.Bar(
        name="Avg Tip", x=dist_agg["dist_bucket"], y=dist_agg["avg_tip"],
        marker_color="#555", marker_line_width=0,
    ))
    fig4.update_layout(
        **PLOTLY_LAYOUT, height=280, barmode="group",
        legend=dict(orientation="h", y=1.05, x=0, font=dict(size=11)),
    )
    fig4.update_yaxes(tickprefix="$")
    st.plotly_chart(fig4, use_container_width=True)

# ── Row 3: Rush hour comparison + Tip distribution ───────────────────────────
col_c, col_d = st.columns(2)

with col_c:
    st.markdown("<div class='section-title'>Peak Period Comparison</div>", unsafe_allow_html=True)
    def period(h):
        if 7 <= h <= 9:   return "Morning Rush"
        if 17 <= h <= 19: return "Evening Rush"
        return "Off-peak"
    dff2 = dff.copy()
    dff2["period"] = dff2["pickup_hour"].apply(period)
    peak = (
        dff2.groupby("period")
        .agg(trips=("fare_amount", "count"), avg_fare=("fare_amount", "mean"))
        .reset_index()
    )
    fig5 = px.bar(
        peak, x="period", y="trips",
        color="period",
        color_discrete_map={
            "Morning Rush": YELLOW, "Evening Rush": "#c8a000", "Off-peak": "#444"
        },
        text=peak["avg_fare"].apply(lambda x: f"${x:.2f} avg"),
    )
    fig5.update_traces(marker_line_width=0, textposition="outside",
                       textfont=dict(size=11, color=MUTED))
    fig5.update_layout(**PLOTLY_LAYOUT, height=280, showlegend=False)
    fig5.update_yaxes(tickformat=",")
    st.plotly_chart(fig5, use_container_width=True)

with col_d:
    st.markdown("<div class='section-title'>Tip % Distribution (Credit Card)</div>",
                unsafe_allow_html=True)
    cc_tips = dff[dff["payment_label"] == "Credit Card"]["tip_pct"].clip(0, 50)
    fig6 = go.Figure(go.Histogram(
        x=cc_tips, nbinsx=50,
        marker_color=YELLOW, marker_line_width=0,
        hovertemplate="Tip: %{x:.1f}%<br>Count: %{y:,}<extra></extra>",
    ))
    fig6.update_layout(**PLOTLY_LAYOUT, height=280)
    fig6.update_xaxes(ticksuffix="%")
    fig6.update_yaxes(tickformat=",")
    st.plotly_chart(fig6, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<span style='color:{MUTED};font-family:DM Mono,monospace;font-size:0.7rem'>"
    f"NYC TLC Yellow Taxi · ELT Pipeline: Apache Airflow + Snowflake · "
    f"Viz: Streamlit + Plotly"
    f"</span>",
    unsafe_allow_html=True,
)
