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

# --- Custom CSS for iPhone 15 Plus ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div[data-testid="stMetricValue"] { font-size: 22px; color: #00FFA3; }
    div[data-testid="stMetricLabel"] { font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.title("🛡️ FCN Mobile Sentinel")
st.caption("Autocallable FCN with Daily KO Logic")

# --- 1. Asset Selection ---
input_tickers = st.text_input("Enter Tickers", "NVDA, TSM, MU, 6857.T")
tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
if not tickers: tickers = ["NVDA"]
ticker = st.selectbox("🎯 Target Asset", tickers)

# --- 2. Robust Data Fetching ---
@st.cache_data(ttl=3600)
def get_asset_info_safe(symbol):
    try:
        asset = yf.Ticker(symbol)
        fast = asset.fast_info
        try:
            full_info = asset.info
            name = full_info.get('longName', symbol)
            pe = full_info.get('trailingPE', 'N/A')
        except:
            name = symbol
            pe = 'N/A'
        
        # 優先抓取 last_price，抓不到則使用 100 做為保險
        price = fast.get('last_price')
        if price is None or price <= 0:
            price = 100.0
            
        return {
            "name": name, "pe": pe,
            "low52": fast.get('yearLow', 0),
            "high52": fast.get('yearHigh', 0),
            "curr": price
        }
    except:
        return {"name": symbol, "pe": "N/A", "low52": 0, "high52": 0, "curr": 100.0}

asset_info = get_asset_info_safe(ticker)
current_p = asset_info['curr']

# --- Asset Profile Card ---
st.subheader(f"🏢 {asset_info['name']}")
st.metric("Current Market Price", f"${current_p:,.2f}") # 顯示現價以利除錯

m1, m2, m3 = st.columns(3)
with m1: st.metric("P/E Ratio", f"{asset_info['pe']:.2f}" if isinstance(asset_info['pe'], (int, float)) else "N/A")
with m2: st.metric("52W Low", f"${asset_info['low52']:,.1f}")
with m3: st.metric("52W High", f"${asset_info['high52']:,.1f}")

st.divider()

# --- 3. Strategy Parameters (含 KO 設定) ---
with st.container():
    st.subheader("⚙️ Strategy Settings")
    strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
    ki_pct = st.slider("Knock-In Barrier (KI %)", 50, 80, 60) / 100
    ko_pct = st.slider("KO Level (Autocall %)", 100, 110, 100) / 100
    coupon = st.number_input("Annualized Coupon (%)", value=12.0)

# 顯示絕對價格（確保不是 100 元）
c1, c2, c3 = st.columns(3)
with c1: st.metric("Target Strike", f"${current_p * strike_pct:,.2f}")
with c2: st.metric("Target KI", f"${current_p * ki_pct:,.2f}")
with c3: st.metric("KO Level", f"${current_p * ko_pct:,.2f}")

# --- 4. Volatility Engine ---
vol_mode = st.radio("Volatility Period", ["30D (Sentinel)", "180D (Bank)"], horizontal=True)
hist_data = yf.Ticker(ticker).history(period="1mo" if "30D" in vol_mode else "6mo")
if len(hist_data) > 10:
    log_returns = np.log(hist_data['Close'] / hist_data['Close'].shift(1))
    sigma = log_returns.std() * np.sqrt(252)
    sigma = max(min(sigma, 0.99), 0.1)
else:
    sigma = 0.35

st.caption(f"📊 Mode: {vol_mode} | Annual Volatility: {sigma:.1%}")

# --- 5. Monte Carlo Simulation with KO/KI Logic ---
n_days, n_paths, dt, mu = 180, 100, 1/252, 0.05
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    shocks = np.random.standard_t(df=3, size=n_paths) * 0.7 
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)

# 統計數據
ko_count = 0
ki_count = 0
for j in range(n_paths):
    path = paths[:, j]
    # 一個月後（21天）每日比價 KO
    triggered_ko = False
    for t in range(21, n_days):
        if path[t] >= ko_pct:
            ko_count += 1
            triggered_ko = True
            break
    # 若沒被 KO 且曾觸發 KI
    if not triggered_ko:
        if np.min(path) <= ki_pct:
            ki_count += 1

ko_prob = (ko_count / n_paths) * 100
win_rate = ((n_paths - ki_count) / n_paths) * 100

# --- 6. Plotting (20% - 200%) ---
fig = go.Figure()
for j in range(n_paths):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', 
                             line=dict(width=0.5, color='rgba(100, 150, 255, 0.3)'), showlegend=False))

fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=ko_pct, line_dash="dash", line_color="#00FFA3", annotation_text="KO Level")
fig.add_hline(y=strike_pct, line_dash="dash", line_color="orange", annotation_text="Strike")
fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="KI Barrier")

fig.update_layout(
    height=380, template="plotly_dark",
    xaxis_title="Days", yaxis_title="Price Ratio",
    yaxis=dict(range=[0.2, 2.0], tickformat=".0%"),
    margin=dict(l=5, r=5, t=10, b=5)
)
st.plotly_chart(fig, use_container_width=True)

# --- 7. Result Card ---
st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 15px; border-radius: 12px; border: 2px solid #00FFA3; text-align: center;">
        <div style="display: flex; justify-content: space-around;">
            <div>
                <p style="color: #00FFA3; font-size: 14px; margin:0;">🚀 KO Probability</p>
                <p style="color: #FFF; font-size: 24px; font-weight: bold;">{ko_prob:.1f}%</p>
            </div>
            <div>
                <p style="color: #FF4B4B; font-size: 14px; margin:0;">🛡️ Win Rate (No KI)</p>
                <p style="color: #FFF; font-size: 24px; font-weight: bold;">{win_rate:.1f}%</p>
            </div>
        </div>
        <p style="color: #888; font-size: 11px; margin-top:10px;">Autocall Observation: Daily from Day 21</p>
    </div>
    """, unsafe_allow_html=True)

# --- 8. Export PDF ---
if st.button("🚀 Export FCN Audit Report"):
    st.balloons()
    audit_no = random.randint(100000, 999999)
    class PDF(FPDF):
        def header(self):
            self.set_fill_color(20, 20, 20); self.rect(0, 0, 210, 40, 'F')
            self.set_text_color(255, 255, 255); self.set_font('Arial', 'B', 18)
            self.cell(0, 20, 'FCN STRATEGY AUDIT REPORT', 0, 1, 'C')
            self.ln(25)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f' [I] ASSET: {asset_info["name"]} ({ticker})', 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f'  - Current Price: ${current_p:,.2f}', ln=True)
    pdf.cell(0, 7, f'  - Annualized Vol: {sigma:.1%}', ln=True)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' [II] PARAMETERS', 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f'  - Strike: {strike_pct*100:.1f}% (${current_p*strike_pct:,.2f})', ln=True)
    pdf.cell(0, 7, f'  - KI Barrier: {ki_pct*100:.1f}% (${current_p*ki_pct:,.2f})', ln=True)
    pdf.cell(0, 7, f'  - KO Level: {ko_pct*100:.1f}% (${current_p*ko_pct:,.2f})', ln=True)
    pdf.ln(5)
    pdf.set_text_color(0, 150, 0)
    pdf.cell(0, 10, f'  >>> KO PROBABILITY: {ko_prob:.1f}%', ln=True)
    pdf.cell(0, 10, f'  >>> WIN RATE (NO KI): {win_rate:.1f}%', ln=True)
    
    pdf_out = pdf.output(dest='S').encode('latin-1')
    b64 = base64.b64encode(pdf_out).decode()
    st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="FCN_Audit_{ticker}.pdf" style="text-decoration:none;"><div style="background-color:#00FFA3;color:black;padding:15px;border-radius:10px;text-align:center;font-weight:bold;">⬇️ Download Audit Report</div></a>', unsafe_allow_html=True)
