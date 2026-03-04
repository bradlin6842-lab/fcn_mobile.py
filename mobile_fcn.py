import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import random
import base64
from fpdf import FPDF

# --- Page Configuration ---
st.set_page_config(page_title="FCN Sentinel Pro", layout="centered")

# --- Custom CSS for iPhone Display ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div[data-testid="stMetricValue"] { font-size: 22px; color: #00FFA3; }
    div[data-testid="stMetricLabel"] { font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.title("🛡️ FCN Mobile Sentinel Pro")

# --- 1. Asset Selection ---
input_tickers = st.text_input("Enter Tickers (e.g., NVDA, TSM, 6857.T, 9988.HK)", "NVDA, TSM, 6857.T, 9988.HK")
tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
if not tickers: tickers = ["NVDA"]
ticker = st.selectbox("🎯 Target Asset", tickers)

# --- 2. Robust Data Fetching ---
@st.cache_data(ttl=60)
def get_asset_info_safe(symbol):
    try:
        asset = yf.Ticker(symbol)
        
        # 1. 第一層：嘗試抓最近 1 天的 1 分鐘 K 線 (對美、港、日股最穩)
        hist = asset.history(period="1d", interval="1m")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
        else:
            # 2. 第二層：K 線抓不到，試 fast_info
            price = asset.fast_info.get('last_price')
            
        # 3. 第三層：如果還是無效值 (None, 0 或 預設 100)，改抓 info
        if price is None or price <= 0 or price == 100.0:
            price = asset.info.get('regularMarketPrice', 100.0)

        # 抓取基本資訊
        full_info = asset.info
        return {
            "name": full_info.get('longName', symbol),
            "pe": full_info.get('trailingPE', 'N/A'),
            "low52": asset.fast_info.get('yearLow', 0),
            "high52": asset.fast_info.get('yearHigh', 0),
            "curr": price
        }
    except:
        return {"name": symbol, "pe": "N/A", "low52": 0, "high52": 0, "curr": 100.0}

asset_info = get_asset_info_safe(ticker)
current_p = asset_info['curr']

# Display Asset Profile
st.subheader(f"🏢 {asset_info['name']}")
m1, m2, m3 = st.columns(3)
with m1: st.metric("P/E Ratio", f"{asset_info['pe']:.2f}" if isinstance(asset_info['pe'], (int, float)) else "N/A")
with m2: st.metric("52W Low", f"${asset_info['low52']:,.1f}")
with m3: st.metric("52W High", f"${asset_info['high52']:,.1f}")

st.divider()

# --- 3. Strategy Parameters ---
with st.container():
    st.subheader("⚙️ Strategy Settings")
    strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
    ki_pct = st.slider("Knock-In Barrier (KI %)", 50, 80, 60) / 100
    coupon = st.number_input("Annualized Coupon (%)", value=12.0)

c1, c2 = st.columns(2)
with c1: st.metric(f"Target Strike", f"${current_p * strike_pct:,.2f}")
with c2: st.metric(f"Target KI Barrier", f"${current_p * ki_pct:,.2f}")

# --- 4. Volatility Engine ---
st.subheader("📉 Risk Path Simulation")
vol_mode = st.radio("Volatility Period", ["30D (Sentinel)", "180D (Bank)"], horizontal=True)
period_map = {"30D (Sentinel)": "1mo", "180D (Bank)": "6mo"}

hist_data = yf.Ticker(ticker).history(period=period_map[vol_mode])
if len(hist_data) > 10:
    log_returns = np.log(hist_data['Close'] / hist_data['Close'].shift(1))
    sigma = log_returns.std() * np.sqrt(252)
    sigma = max(min(sigma, 1.2), 0.1)
else:
    sigma = 0.35

st.caption(f"📊 Mode: {vol_mode} | Annual Volatility: {sigma:.1%}")

# --- 5. Monte Carlo Simulation ---
n_days, n_paths, dt, mu = 180, 100, 1/252, 0.05
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    shocks = np.random.standard_t(df=3, size=n_paths) * 0.7 
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)

# --- 6. Plotting (Updated Y-Axis Range: 20% - 200%) ---
fig = go.Figure()
for j in range(n_paths):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', 
                             line=dict(width=0.5, color='rgba(100, 150, 255, 0.3)'), showlegend=False))

fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=strike_pct, line_dash="dash", line_color="orange", annotation_text="Strike")
fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="KI Barrier")

fig.update_layout(
    height=350, template="plotly_dark",
    xaxis_title="Forward Days", yaxis_title="Price Ratio",
    # 關鍵修改：設定 Y 軸範圍為 0.2 到 2.0，並顯示為百分比
    yaxis=dict(range=[0.2, 2.0], tickformat=".0%"), 
    margin=dict(l=5, r=5, t=10, b=5)
)
st.plotly_chart(fig, use_container_width=True)

# --- 7. Probability Card ---
no_touch_count = sum(1 for j in range(n_paths) if np.min(paths[:, j]) > ki_pct)
win_rate = (no_touch_count / n_paths) * 100

st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 15px; border-radius: 12px; border: 2px solid #00FFA3; text-align: center; margin-bottom: 20px;">
        <p style="color: #00FFA3; font-size: 16px; margin: 0;">🏆 Est. Win Rate (No KI Event)</p>
        <p style="color: #FFFFFF; font-size: 32px; font-weight: bold; margin: 5px 0;">{win_rate:.1f}%</p>
        <p style="color: #888888; font-size: 11px;">Simulation: 100 paths | Student's t-dist</p>
    </div>
    """, unsafe_allow_html=True)

