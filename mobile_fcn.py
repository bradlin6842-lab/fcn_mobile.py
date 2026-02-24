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

# --- Custom CSS for Dark Theme & Metrics ---
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
input_tickers = st.text_input("Enter Ticker Symbols (e.g., NVDA, 6857.T, 0700.HK)", "NVDA, TSM, 6857.T")
tickers = [t.strip().upper() for t in input_tickers.split(",")]
ticker = st.selectbox("🎯 Target Asset", tickers)

# --- 2. Enhanced Data Fetching (Fundamentals) ---
@st.cache_data(ttl=3600)
def get_asset_info(symbol):
    asset = yf.Ticker(symbol)
    info = asset.info
    return {
        "name": info.get('longName', symbol),
        "pe": info.get('trailingPE', 'N/A'),
        "low52": info.get('fiftyTwoWeekLow', 0),
        "high52": info.get('fiftyTwoWeekHigh', 0),
        "curr": info.get('regularMarketPrice') or info.get('previousClose', 100.0)
    }

asset_info = get_asset_info(ticker)
current_p = asset_info['curr']

# Display Company Profile
st.subheader(f"🏢 {asset_info['name']}")
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("P/E Ratio", f"{asset_info['pe']:.2f}" if isinstance(asset_info['pe'], (int, float)) else "N/A")
with m2:
    st.metric("52W Low", f"${asset_info['low52']:,.1f}")
with m3:
    st.metric("52W High", f"${asset_info['high52']:,.1f}")

st.divider()

# --- 3. Strategy Parameters ---
with st.container():
    st.subheader("⚙️ Strategy Settings")
    strike_pct = st.slider("Strike Price (%)", 50, 100, 80) / 100
    ki_pct = st.slider("Knock-In Barrier (KI %)", 30, 80, 60) / 100
    coupon = st.number_input("Annualized Coupon (%)", value=12.0)

c1, c2 = st.columns(2)
with c1:
    st.metric(f"Target Strike", f"${current_p * strike_pct:,.2f}")
with c2:
    st.metric(f"Target KI Barrier", f"${current_p * ki_pct:,.2f}")

# --- 4. Volatility Engine (Dual Mode) ---
st.subheader("📉 Risk Path Simulation")
vol_mode = st.radio("Volatility Lookup Period", ["30D (Sentinel)", "180D (Bank Std)"], horizontal=True)
period_map = {"30D (Sentinel)": "1mo", "180D (Bank Std)": "6mo"}

hist_data = yf.Ticker(ticker).history(period=period_map[vol_mode])
if len(hist_data) > 10:
    log_returns = np.log(hist_data['Close'] / hist_data['Close'].shift(1))
    sigma = log_returns.std() * np.sqrt(252)
    sigma = max(min(sigma, 0.9), 0.1)
else:
    sigma = 0.32

st.caption(f"📊 Mode: {vol_mode} | Annual Volatility: {sigma:.1%}")

# --- 5. Monte Carlo Simulation (Student's t for Tail Risk) ---
n_days, n_paths, dt, mu = 180, 100, 1/252, 0.05
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    # df=3 simulates fat tails (higher probability of extreme moves)
    shocks = np.random.standard_t(df=3, size=n_paths) * 0.7 
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)

# --- 6. Plotting ---
fig = go.Figure()
for j in range(n_paths):
    fig.add_trace(go.Scatter(y=paths[:, j], mode='lines', line=dict(width=0.5, color='rgba(100, 150, 255, 0.3)'), showlegend=False))

fig.add_hline(y=1.0, line_color="white", line_width=2)
fig.add_hline(y=strike_pct, line_dash="dash", line_color="orange")
fig.add_hline(y=ki_pct, line_dash="dot", line_color="red")

fig.update_layout(
    height=350, template="plotly_dark",
    xaxis_title="Forward Trading Days", yaxis_title="Price Ratio",
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

# --- 8. Professional PDF Report ---
if st.button("🚀 Generate Audit Certificate"):
    st.balloons()
    audit_no = random.randint(100000, 999999)
    
    class PDF(FPDF):
        def header(self):
            self.set_fill_color(20, 20, 20)
            self.rect(0, 0, 210, 40, 'F')
            self.set_text_color(255, 255, 255)
            self.set_font('Arial', 'B', 18)
            self.cell(0, 20, 'FCN STRATEGY AUDIT REPORT', 0, 1, 'C')
            self.set_font('Arial', 'I', 10)
            self.cell(0, -5, f'Certificate ID: #{audit_no}', 0, 1, 'C')
            self.ln(25)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'FCN Sentinel Pro | Internal Analysis Report', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    # Section I: Profile
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f' [I] ASSET PROFILE: {asset_info["name"]} ({ticker})', 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 11)
    pdf.ln(3)
    pdf.cell(0, 7, f'  - Valuation (P/E Ratio): {asset_info["pe"]}', ln=True)
    pdf.cell(0, 7, f'  - 52-Week Range: ${asset_info["low52"]:,.1f} - ${asset_info["high52"]:,.1f}', ln=True)
    pdf.cell(0, 7, f'  - Current Market Price: ${current_p:,.2f}', ln=True)
    pdf.ln(5)

    # Section II: Setup
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' [II] STRATEGY PARAMETERS', 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 11)
    pdf.ln(3)
    pdf.cell(0, 7, f'  - Strike Price: {strike_pct*100:.1f}% (${current_p*strike_pct:,.2f})', ln=True)
    pdf.cell(0, 7, f'  - Knock-In Barrier: {ki_pct*100:.1f}% (${current_p*ki_pct:,.2f})', ln=True)
    pdf.cell(0, 7, f'  - Annualized Coupon: {coupon:.2f}%', ln=True)
    pdf.ln(5)

    # Section III: Simulation
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' [III] RISK SIMULATION SUMMARY', 0, 1, 'L', fill=True)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 14)
    status_color = (0, 128, 0) if win_rate > 80 else (200, 0, 0)
    pdf.set_text_color(*status_color)
    pdf.cell(0, 10, f'  >>> ESTIMATED WIN RATE: {win_rate:.1f}%', ln=True)
    
    pdf.set_text_color(80, 80, 80)
    pdf.set_font('Arial', 'I', 9)
    pdf.multi_cell(0, 6, 'Disclaimer: This simulation uses a Student\'s t-distribution to model potential fat-tail risks (Black Swan events). This is a mathematical estimation and does not guarantee future results.')

    # PDF Output Logic
    pdf_output = pdf.output(dest='S').encode('latin-1')
    b64_pdf = base64.b64encode(pdf_output).decode()
    download_link = f'<a href="data:application/pdf;base64,{b64_pdf}" download="FCN_PRO_{ticker}_{audit_no}.pdf" style="text-decoration:none;"><div style="background-color:#2ECC71;color:white;padding:15px;border-radius:10px;text-align:center;font-weight:bold;">⬇️ Download Pro Audit Report</div></a>'
    st.markdown(download_link, unsafe_allow_html=True)
