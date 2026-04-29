import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="FCN Sentinel Pro", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #00FFA3; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ FCN Mobile Sentinel")

# --- 1. Data Fetching (四層強效抓取) ---
input_tickers = st.text_input("Enter Tickers", "NVDA, TSM, 6857.T, 0700.HK")
tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
ticker = st.selectbox("🎯 Target Asset", tickers if tickers else ["NVDA"])

@st.cache_data(ttl=60)
def get_asset_info_ultra(symbol):
    try:
        asset = yf.Ticker(symbol)
        # 優先權 1: 抓取 1分鐘歷史資料的最後一筆收盤價
        hist = asset.history(period="1d", interval="1m")
        price = hist['Close'].iloc[-1] if not hist.empty else None
        
        # 優先權 2: 若失敗，嘗試 fast_info
        if price is None or price <= 0:
            price = asset.fast_info.get('last_price')
            
        # 優先權 3: 若失敗，嘗試 info 裡的現價
        if price is None or price <= 0 or price == 100:
            price = asset.info.get('regularMarketPrice')

        # 優先權 4: 最終保險 (Fallback)
        if price is None: price = 100.0

        info = asset.info
        fast = asset.fast_info
        return {
            "name": info.get('longName', symbol),
            "curr": price,
            "fpe": info.get('forwardPE', 'N/A'),
            "low52": fast.get('yearLow', 'N/A'),
            "high52": fast.get('yearHigh', 'N/A')
        }
    except:
        return {"name": symbol, "curr": 100.0, "fpe": "N/A", "low52": "N/A", "high52": "N/A"}

asset_info = get_asset_info_ultra(ticker)
current_p = asset_info['curr']

st.subheader(f"🏢 {asset_info['name']}")
st.metric("Real-time Market Price", f"${current_p:,.2f}") 

m1, m2, m3 = st.columns(3)
with m1: st.metric("Forward P/E", f"{asset_info['fpe']:.2f}" if isinstance(asset_info['fpe'], (int, float)) else "N/A")
with m2: st.metric("52W Low", f"${asset_info['low52']:,.1f}" if isinstance(asset_info['low52'], (int, float)) else "N/A")
with m3: st.metric("52W High", f"${asset_info['high52']:,.1f}" if isinstance(asset_info['high52'], (int, float)) else "N/A")

st.divider()

# --- 2. Strategy Settings ---
no_ki_mode = st.toggle("🛡️ No KI Mode", value=False)
strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
ki_pct = 0.0 if no_ki_mode else st.slider("KI Barrier (%)", 30, 95, 60) / 100
ko_pct = st.slider("KO Level (%)", 80, 110, 103) / 100

c1, c2, c3 = st.columns(3)
with c1: st.metric("Target Strike", f"${current_p * strike_pct:,.2f}")
with c2: st.metric("Target KI", "N/A" if no_ki_mode else f"${current_p * ki_pct:,.2f}")
with c3: st.metric("KO Level", f"${current_p * ko_pct:,.2f}")

# --- 3. Simulation (500 Paths) ---
vol_mode = st.radio("Volatility Period", ["30D (Sentinel)", "180D (Bank)"], horizontal=True)
hist_all = yf.Ticker(ticker).history(period="1y")
if len(hist_all) > 180:
    target_hist = hist_all.tail(30 if "30D" in vol_mode else 180)
    sigma = np.log(target_hist['Close'] / target_hist['Close'].shift(1)).std() * np.sqrt(252)
else:
    sigma = 0.45

n_days, n_paths, dt, mu = 180, 500, 1/252, 0.05
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    Z = 0.8 * np.random.normal(0, 1, n_paths) + 0.2 * np.random.standard_t(df=3, size=n_paths)
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z)

ki_event_count = 0
for j in range(n_paths):
    if np.min(paths[:, j]) <= ki_pct: ki_event_count += 1
win_rate = ((n_paths - ki_event_count) / n_paths) * 100

# --- 4. Plotting & Result ---
fig = go.Figure()
for j in range(min(n_paths, 120)):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', line=dict(width=0.4, color='rgba(100, 150, 255, 0.2)'), showlegend=False))
fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=ko_pct, line_dash="dash", line_color="#00FFA3", annotation_text="KO Ref")
if not no_ki_mode: fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="KI")
fig.update_layout(height=380, template="plotly_dark", yaxis=dict(range=[0.1, 2.2], tickformat=".0%"), margin=dict(l=5, r=5, t=10, b=5))
st.plotly_chart(fig, use_container_width=True)

st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 2px solid #00FFA3; text-align: center;">
        <p style="color: #00FFA3; font-size: 16px; margin:0;">🛡️ Estimated Win Rate (No KI)</p>
        <p style="color: #FFFFFF; font-size: 36px; font-weight: bold;">{win_rate:.1f}%</p>
    </div>
    """, unsafe_allow_html=True)
