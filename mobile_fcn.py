import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="FCN Sentinel Pro", layout="centered")

st.markdown("<style>.main { background-color: #0E1117; } div[data-testid='stMetricValue'] { font-size: 22px; color: #00FFA3; }</style>", unsafe_allow_html=True)

st.title("🛡️ FCN Mobile Sentinel")

# --- 1. Data Fetching ---
input_tickers = st.text_input("Enter Tickers", "NVDA, TSM, MU, 6857.T")
tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
ticker = st.selectbox("🎯 Target Asset", tickers if tickers else ["NVDA"])

@st.cache_data(ttl=300)
def get_asset_info_robust(symbol):
    try:
        asset = yf.Ticker(symbol)
        hist = asset.history(period="5d")
        price = hist['Close'].iloc[-1] if not hist.empty else 100.0
        return {"name": asset.info.get('longName', symbol), "curr": price}
    except:
        return {"name": symbol, "curr": 100.0}

asset_info = get_asset_info_robust(ticker)
current_p = asset_info['curr']

st.subheader(f"🏢 {asset_info['name']}")
st.metric("Current Market Price", f"${current_p:,.2f}") 

st.divider()

# --- 2. Strategy Settings ---
strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
ki_pct = st.slider("Knock-In Barrier (KI %)", 50, 95, 80) / 100 # 擴大範圍方便測試
ko_pct = st.slider("KO Level (Autocall %)", 85, 110, 103) / 100

st.metric("Target KI Barrier Price", f"${current_p * ki_pct:,.2f}")

# --- 3. Volatility Selection ---
vol_mode = st.radio("Volatility Period", ["30D (Sentinel)", "180D (Bank)"], horizontal=True)
hist_data = yf.Ticker(ticker).history(period="1y")

if len(hist_data) > 180:
    target_data = hist_data.tail(30 if "30D" in vol_mode else 180)
    sigma = np.log(target_data['Close'] / target_data['Close'].shift(1)).std() * np.sqrt(252)
else:
    sigma = 0.45

st.caption(f"📊 {vol_mode} Annual Volatility: {sigma:.1%}")

# --- 4. Monte Carlo (提升至 500 條路徑) ---
n_days, n_paths, dt, mu = 180, 500, 1/252, 0.05
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    # 使用標準 GBM 公式，確保高波動標的會產生劇烈跌幅
    shocks = np.random.normal(0, 1, n_paths)
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)

# 統計 KI
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

# --- 5. Plotting (取前 100 條繪圖避免手機卡頓，但計算用 500 條) ---
fig = go.Figure()
for j in range(min(n_paths, 100)):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', line=dict(width=0.4, color='rgba(100, 150, 255, 0.2)'), showlegend=False))
fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=ko_pct, line_dash="dash", line_color="#00FFA3", annotation_text="KO Ref")
fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="KI Barrier")
fig.update_layout(height=380, template="plotly_dark", yaxis=dict(range=[0.2, 2.0], tickformat=".0%"), margin=dict(l=5, r=5, t=10, b=5))
st.plotly_chart(fig, use_container_width=True)

# --- 6. Result Card ---
st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 2px solid #00FFA3; text-align: center;">
        <p style="color: #00FFA3; font-size: 16px; margin:0;">🛡️ Estimated Win Rate</p>
        <p style="color: #FFFFFF; font-size: 36px; font-weight: bold; margin: 5px 0;">{win_rate:.1f}%</p>
        <p style="color: #888888; font-size: 11px;">Simulation based on 500 daily paths.</p>
    </div>
    """, unsafe_allow_html=True)
