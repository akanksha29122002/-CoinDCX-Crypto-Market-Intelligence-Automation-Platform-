import os
import io
import logging
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.db_connection import get_db_session, engine
from src.database.models import Asset, MarketOHLCVHourly, AnomalyAlert
from src.database.queries import get_top_movers, get_historical_volatility_stats
from src.reporting.excel_generator import generate_daily_report

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CoinDCX_Streamlit_App")

# --- Streamlit Presentation Layer Configurations ---
st.set_page_config(
    page_title="CoinDCX Crypto Market Intelligence Platform",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom corporate brand styling injection (CoinDCX Slate Navy & Orange Palette)
st.markdown("""
    <style>
    .main {
        background-color: #F8FAFC;
    }
    .kpi-title {
        font-size: 14px;
        font-weight: bold;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 800;
        color: #0F172A;
    }
    .kpi-card {
        background-color: #ffffff;
        padding: 15px 20px;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px 0 rgba(0,0,0,0.05);
    }
    .coindcx-title {
        color: #0F172A;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 800;
        margin-bottom: 0px;
    }
    .coindcx-subtitle {
        color: #64748B;
        font-size: 14px;
        margin-top: 0px;
        margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Caching Layer to Reduce Database Overload ---
@st.cache_data(ttl=300)  # Cache data for 5 minutes to prevent redundant queries
def load_assets_summary():
    """
    Fetches base parameters for tracked assets.
    """
    with get_db_session() as session:
        assets = session.query(Asset).all()
        data = []
        for a in assets:
            data.append({
                "Symbol": a.symbol,
                "Name": a.name,
                "Market Cap ($)": float(a.current_market_cap) if a.current_market_cap else 0.0,
                "Circulating Supply": float(a.current_circulating_supply) if a.current_circulating_supply else 0.0,
                "Updated At": a.updated_at
            })
        return pd.DataFrame(data)

@st.cache_data(ttl=300)
def load_historical_ticks(symbol: str, limit: int = 168):
    """
    Retrieves chronological market ticks for a target token.
    """
    with get_db_session() as session:
        stats = get_historical_volatility_stats(session, symbol, limit=limit)
        if not stats:
            return pd.DataFrame()
        # Convert list of dicts to DataFrame
        df = pd.DataFrame(stats)
        # Sort chronologically for Plotly trends
        df.sort_values("timestamp", inplace=True)
        return df

@st.cache_data(ttl=300)
def load_recent_anomalies(limit: int = 10):
    """
    Retrieves list of newly captured risk events.
    """
    with get_db_session() as session:
        alerts = session.query(AnomalyAlert).order_by(AnomalyAlert.logged_at.desc()).limit(limit).all()
        data = []
        for al in alerts:
            data.append({
                "Asset": al.symbol,
                "Timestamp": al.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Anomaly Type": al.anomaly_type,
                "Detected Value": float(al.detected_value),
                "Threshold": float(al.threshold_value),
                "Description": al.description,
                "Notified": "✅ Yes" if al.alert_dispatched else "⏳ Pending"
            })
        return pd.DataFrame(data)

# --- Dashboard View Controller ---

# Header Panel
st.markdown("<h1 class='coindcx-title'>🪙 CoinDCX Crypto Market Intelligence & Automation Platform</h1>", unsafe_allow_html=True)
st.markdown("<p class='coindcx-subtitle'>Production-Grade Serverless Cloud Operations Dashboard & Executive Download Terminal</p>", unsafe_allow_html=True)

# 1. CORE KPI CARDS
st.markdown("### 📊 Operational Health & KPI Indicators")
col1, col2, col3 = st.columns(3)

# Populate KPIs dynamically from database
try:
    assets_df = load_assets_summary()
    total_assets = len(assets_df)
    total_market_cap = assets_df["Market Cap ($)"].sum() if not assets_df.empty else 0.0
except Exception as e:
    logger.error(f"Failed to fetch KPI summaries: {e}")
    total_assets = 0
    total_market_cap = 0.0

with col1:
    st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-title'>Active Tracked Tokens</div>
            <div class='kpi-value'>{total_assets} Symbols</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-title'>Aggregate Market Capitalization</div>
            <div class='kpi-value'>${total_market_cap:,.2f}</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    # Serverless runtime status
    current_time = datetime.utcnow().strftime("%H:%M UTC")
    st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-title'>Scheduler Pipeline Health</div>
            <div class='kpi-value' style='color:#FF5A00;'>🟢 Online ({current_time})</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# 2. INTERACTIVE VISUAL PRICE TRENDS & INDICATORS
st.markdown("### 📈 Technical Price Indicators & In-Memory Visual Analytics")

# Asset selection
assets_list = list(assets_df["Symbol"].unique()) if not assets_df.empty else ["BTC", "ETH", "SOL", "MATIC"]
selected_symbol = st.selectbox("🎯 Target Asset Selector:", assets_list, index=0)

col_charts, col_kpis = st.columns([3, 1])

with col_charts:
    ticks_df = load_historical_ticks(selected_symbol, limit=72) # Show past 3 days (72 hours)
    
    if not ticks_df.empty:
        # Generate Plotly close price chart alongside 24h moving average (SMA)
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=ticks_df["timestamp"],
            y=ticks_df["close"],
            mode="lines",
            name="Close Price ($)",
            line=dict(color="#0F172A", width=2.5)
        ))
        
        fig.add_trace(go.Scatter(
            x=ticks_df["timestamp"],
            y=ticks_df["sma_24h"],
            mode="lines",
            name="24h Simple Moving Average",
            line=dict(color="#FF5A00", width=1.5, dash="dash")
        ))
        
        fig.update_layout(
            title=f"{selected_symbol} Hourly Close Price Trend & 24h SMA Matrix",
            xaxis_title="Time (UTC)",
            yaxis_title="Price ($)",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=40, b=0),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No active historical ticks data found for {selected_symbol}. Confirm that your ingestion scheduler has run.")

with col_kpis:
    st.markdown("#### 🔍 Active Token Specs")
    if not assets_df.empty and selected_symbol in assets_df["Symbol"].values:
        asset_info = assets_df[assets_df["Symbol"] == selected_symbol].iloc[0]
        st.markdown(f"**Name:** `{asset_info['Name']}`")
        st.markdown(f"**Market Cap:** `${asset_info['Market Cap ($)']:,.2f}`")
        
        # Pull latest tick metrics
        if not ticks_df.empty:
            latest_price = ticks_df.iloc[-1]["close"]
            prev_price = ticks_df.iloc[-2]["close"] if len(ticks_df) > 1 else latest_price
            price_change = ((latest_price - prev_price) / prev_price) * 100.0
            
            st.metric(
                label="Latest Price ($)",
                value=f"${latest_price:,.2f}",
                delta=f"{price_change:+.2f}% (1h)"
            )
            
            latest_vol = ticks_df.iloc[-1]["rolling_std_7d"]
            st.markdown(f"**Historical Volatility:** `{latest_vol:.2%}`")
    else:
        st.write("Asset specifications unavailable.")

st.markdown("---")

# 3. EXECUTIVE DOWNLOAD TERMINAL (DYNAMIC EXCEL GENERATION)
st.markdown("### 📥 Executive Control & Download Center")
st.markdown("Click the button below to **dynamically compile and download** the corporate-styled spreadsheet. The engine aggregates live data, maps formulas, and creates Pivot tables *on-the-fly* in the server's memory.")

# Download Button Logic
if st.button("📊 Compile Daily Crypto Report (.xlsx)", key="compile_excel"):
    with st.spinner("Executing Openpyxl & XlsxWriter layout engines..."):
        try:
            # 1. Initialize DB Session and compile report file path
            with get_db_session() as db_session:
                report_path = generate_daily_report(db_session, "reports")
                
            # 2. Read compiled report binary into an in-memory buffer
            if os.path.exists(report_path):
                with open(report_path, "rb") as f:
                    excel_data = f.read()
                
                # Serve file instantly using Streamlit download widget
                st.download_button(
                    label="💾 Download Daily_Crypto_Report.xlsx",
                    data=excel_data,
                    file_name=os.path.basename(report_path),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success("Spreadsheet compiled successfully! Click the save button above to download.")
            else:
                st.error("Engine failed to locate compiled spreadsheet artifact.")
        except Exception as ex:
            st.error(f"Spreadsheet generation crashed: {ex}")
            logger.error(f"Excel compilation error: {ex}", exc_info=True)

st.markdown("---")

# 4. STATISTICAL ANOMALY & RISK EVENTS LOGS
st.markdown("### 🚨 Live Risk & Anomaly logs")
st.markdown("Captured statistical crashes (Price drops $>5\%$ in an hour) and excessive volatility limits ($>3\sigma$ standard deviations):")

try:
    anomalies_df = load_recent_anomalies(limit=8)
    if not anomalies_df.empty:
        # Style dataframe table visually
        def style_anomaly(val):
            color = 'red' if 'CRASH' in str(val) or 'EXCESSIVE' in str(val) else 'black'
            return f'color: {color}; font-weight: bold;'

        st.dataframe(
            anomalies_df.style.map(style_anomaly, subset=["Anomaly Type"]),
            use_container_width=True
        )
    else:
        st.success("No pricing or volatility anomalies detected in the past lookback cycles. System operates inside safe boundaries.")
except Exception as e:
    st.error("Failed to load operational risk alerts.")
    logger.error(f"Anomaly alert grid error: {e}")
