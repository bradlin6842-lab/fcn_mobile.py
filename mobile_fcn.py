import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(page_title="FCN Sentinel Pro", layout="centered")

# --- Custom CSS for Mobile ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #00FFA3; font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: 14px; }
    .stSlider { padding-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.title("🛡️ FCN Mobile Sentinel")
st.caption("Professional Structured Product Risk Monitor")

# --- 1. Asset Selection ---
input_tickers = st.text_input("Enter Tickers (e.g. NVDA, 6857.T, 0700.HK)", "NVDA, TSM, 6857.T, 0700.HK")
tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
ticker = st.selectbox("🎯 Target Asset", tickers if tickers else ["NVDA"])

# --- 2. Robust Data Fetching (找回 P/E 與 52W 數據) ---
@st.cache_data(ttl=60)
def get_asset_info_robust(symbol):
    try:
        asset = yf.Ticker(symbol)
        # 第一層：1分鐘 K 線抓取 (最準確現價)
        hist = asset.history(period="1d", interval="1m")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
        else:
            price = asset.fast_info.get('last_price', 100.0)
            
        # 第二層：如果還是 100 或無效，抓取 regularMarketPrice
        if price is None or price <= 0 or price == 100.0:
            price = asset.info.get('regularMarketPrice', 100.0)

        info = asset.info
        fast = asset.fast_info
        
        return {
            "name": info.get('longName', symbol),
            "curr": price,
            "pe": info.get('trailingPE', 'N/A'),
            "low52": fast.get('yearLow', 'N/A'),
            "high52": fast.get('yearHigh', 'N/A')
        }
    except:
        return {"name": symbol, "curr": 100.0, "pe": "N/A", "low52": "N/A", "high52": "N/A"}

asset_info = get_asset_info_robust(ticker)
current_p = asset_info['curr']

# --- Display Asset Profile ---
st.subheader(f"🏢 {asset_info['name']}")
st.metric("Real-time Market Price", f"${current_p:,.2f}") 

# 重新找回的三欄位資訊
m1, m2, m3 = st.columns(3)
with m1: st.metric("P/E Ratio", f"{asset_info['pe']:.2f}" if isinstance(asset_info['pe'], (int, float)) else "N/A")
with m2: st.metric("52W Low", f"${asset_info['low52']:,.1f}" if isinstance(asset_info['low52'], (int, float)) else "N/A")
with m3: st.metric("52W High", f"${asset_info['high52']:,.1f}" if isinstance(asset_info['high52'], (int, float)) else "N/A")

st.divider()

# --- 3. Strategy Settings ---
with st.container():
    st.subheader("⚙️ Strategy Settings")
    
    no_ki_mode = st.toggle("🛡️ No KI Mode (No Downside Barrier)", value=False)
    
    strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
    
    if no_ki_mode:
        ki_pct = 0.0
        st.info("No KI Mode Active: Win rate will be based on price remaining above $0.")
    else:
        ki_pct = st.slider("Knock-In Barrier (KI %)", 30, 95, 60) / 100

    ko_pct = st.slider("KO Level (Autocall %)", 100, 110, 103) / 100

# 顯示金額
c1, c2 = st.columns(2)
with c1: st.metric("Target Strike Price", f"${current_p * strike_pct:,.2f}")
with c2: 
    ki_val = "N/A" if no_ki_mode else f"${current_p * ki_pct:,.2f}"
    st.metric("Target KI Price", ki_val)

# --- 4. Volatility Period ---
st.write("---")
vol_mode = st.radio("Volatility Period", ["30D (Sentinel)", "180D (Bank)"], horizontal=True)
hist_all = yf.Ticker(ticker).history(period="1y")

if len(hist_all) > 180:
    lookback = 30 if "30D" in vol_mode else 180
    target_hist = hist_all.tail(lookback)
    sigma = np.log(target_hist['Close'] / target_hist['Close'].shift(1)).std() * np.sqrt(252)
else:
    sigma = 0.45

st.caption(f"📊 {vol_mode} Annual Volatility: {sigma:.1%}")

# --- 5. Monte Carlo Simulation ---
n_days, n_paths, dt, mu = 180, 500, 1/252, 0.05
paths = np.ones((n_days, n_paths))

for i in range(1, n_days):
    # 混合肥尾分佈增加風險真實性
    Z = 0.8 * np.random.normal(0, 1, n_paths) + 0.2 * np.random.standard_t(df=3, size=n_paths)
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z)

# 嚴格 KI 統計
ki_event_count = 0
for j in range(n_paths):
    if np.min(paths[:, j]) <= ki_pct:
        ki_event_count += 1

win_rate = ((n_paths - ki_event_count) / n_paths) * 100

# --- 6. Plotting ---
fig = go.Figure()
for j in range(min(n_paths, 150)):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', 
                             line=dict(width=0.4, color='rgba(100, 150, 255, 0.2)'), showlegend=False))

fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=ko_pct, line_dash="dash", line_color="#00FFA3", annotation_text="KO Ref")
if not no_ki_mode:
    fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="KI Barrier")

fig.update_layout(
    height=380, template="plotly_dark",
    yaxis=dict(range=[0.1, 2.2], tickformat=".0%"),
    margin=dict(l=5, r=5, t=10, b=5)
)
st.plotly_chart(fig, use_container_width=True)

# --- 7. Result Card ---
st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 15px; border: 2px solid #00FFA3; text-align: center;">
        <p style="color: #00FFA3; font-size: 16px; margin:0;">🛡️ Estimated Win Rate</p>
        <p style="color: #FFFFFF; font-size: 38px; font-weight: bold; margin: 10px 0;">{win_rate:.1f}%</p>
        <p style="color: #888888; font-size: 12px;">Probability of NO KI event during 180 days.</p>
    </div>
    """, unsafe_allow_html=True)
