import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="FCN Sentinel Pro", layout="centered")

# --- Custom CSS ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div[data-testid="stMetricValue"] { font-size: 22px; color: #00FFA3; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ FCN Mobile Sentinel")
st.caption("Focus on Downside Protection (No KO Prob Edition)")

# --- 1. Asset Selection ---
input_tickers = st.text_input("Enter Tickers", "NVDA, TSM, MU, 6857.T")
tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
ticker = st.selectbox("🎯 Target Asset", tickers if tickers else ["NVDA"])

# --- 2. Enhanced Data Fetching ---
@st.cache_data(ttl=300)
def get_asset_info_robust(symbol):
    try:
        asset = yf.Ticker(symbol)
        hist = asset.history(period="5d")
        price = hist['Close'].iloc[-1] if not hist.empty else asset.fast_info.get('last_price', 100.0)
        if price <= 0: price = 100.0
        return {"name": asset.info.get('longName', symbol), "curr": price}
    except:
        return {"name": symbol, "curr": 100.0}

asset_info = get_asset_info_robust(ticker)
current_p = asset_info['curr']

st.subheader(f"🏢 {asset_info['name']}")
st.metric("Current Market Price", f"${current_p:,.2f}") 

st.divider()

# --- 3. Strategy Settings ---
strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
ki_pct = st.slider("Knock-In Barrier (KI %)", 50, 80, 60) / 100
ko_pct = st.slider("KO Level (Autocall %)", 85, 110, 100) / 100

c1, c2 = st.columns(2)
with c1: st.metric("Target Strike", f"${current_p * strike_pct:,.2f}")
with c2: st.metric("Target KI", f"${current_p * ki_pct:,.2f}")

# --- 4. Volatility & Simulation ---
hist_data = yf.Ticker(ticker).history(period="1mo")
sigma = np.log(hist_data['Close'] / hist_data['Close'].shift(1)).std() * np.sqrt(252) if len(hist_data) > 10 else 0.35
st.caption(f"📊 Annual Volatility: {sigma:.1%}")

n_days, n_paths, dt, mu = 180, 100, 1/252, 0.05
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    shocks = np.random.standard_t(df=3, size=n_paths) * 0.7 
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)

# 僅統計 KI 事件
ki_count = 0
for j in range(n_paths):
    path = paths[:, j]
    triggered_ko = False
    for t in range(21, n_days):
        if path[t] >= ko_pct:
            triggered_ko = True
            break
    if not triggered_ko and np.min(path) <= ki_pct:
        ki_count += 1

win_rate = ((n_paths - ki_count) / n_paths) * 100

# --- 5. Plotting ---
fig = go.Figure()
for j in range(n_paths):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', line=dict(width=0.5, color='rgba(100, 150, 255, 0.3)'), showlegend=False))
fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=ko_pct, line_dash="dash", line_color="#00FFA3", annotation_text="KO Reference")
fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="KI Barrier")
fig.update_layout(height=380, template="plotly_dark", yaxis=dict(range=[0.2, 2.0], tickformat=".0%"), margin=dict(l=5, r=5, t=10, b=5))
st.plotly_chart(fig, use_container_width=True)

# --- 6. Result Card (Only Win Rate) ---
st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 2px solid #00FFA3; text-align: center;">
        <p style="color: #00FFA3; font-size: 16px; margin:0;">🛡️ Estimated Win Rate</p>
        <p style="color: #FFFFFF; font-size: 36px; font-weight: bold; margin: 5px 0;">{win_rate:.1f}%</p>
        <p style="color: #888888; font-size: 12px;">Probability of not touching KI before expiry/KO.</p>
    </div>
    """, unsafe_allow_html=True)
