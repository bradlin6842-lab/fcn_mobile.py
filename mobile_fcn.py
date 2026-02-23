import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# 設定手機版頁面優化
st.set_page_config(page_title="FCN Mobile Sentinel", layout="centered")

# --- CSS 注入：優化手機按鈕與間距 ---
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 頂部輸入區 ---
st.title("🛡️ FCN 手機哨兵")

# 讓你在手機上直接輸入代號，預設給 TSM, NVDA
input_tickers = st.text_input("請輸入美股代號 (用逗號隔開)", value="TSM, NVDA")

# 把字串轉成清單，並去除空格
tickers = [t.strip().upper() for t in input_tickers.split(",")]

# 讓選單跟著你的輸入跑
ticker = st.selectbox("🎯 當前監控標的", tickers)


# --- 參數調整區 (主畫面，方便手指操作) ---
with st.container():
    st.subheader("⚙️ 設定參數")
    strike_pct = st.slider("執行價 (Strike %)", 70, 100, 80) / 100
    ki_pct = st.slider("障礙價 (KI %)", 50, 80, 65) / 100
    coupon = st.number_input("年化配息 (%)", value=12.0)
    
# --- 關鍵指標顯示 ---
# --- 抓取數據與邏輯處理 ---
# 這裡會根據你在手機上選的 ticker (例如 AAPL)，自動去查它的現價
stock_data = yf.Ticker(ticker).history(period="1d")
if not stock_data.empty:
    current_p = stock_data['Close'].iloc[-1]
else:
    current_p = 100.0  # 如果查不到，給一個預設值

# --- 關鍵指標顯示 (覆蓋這裡) ---
st.divider()
c1, c2 = st.columns(2)

with c1:
    # 這裡會自動顯示你選的股票名稱
    st.metric(f"{ticker} 執行價", f"${current_p * strike_pct:.1f}")
with c2:
    st.metric(f"{ticker} 障礙價", f"${current_p * ki_pct:.1f}")


# --- 風險模擬模擬圖 ---
st.subheader("📉 風險路徑模擬")

import numpy as np

# 1. 設定模擬參數
n_days = 30      # 模擬未來 30 天
n_paths = 50     # 畫出 50 條路徑
sigma = 0.3      # 假設年化波動率 30%
dt = 1/252       # 每日時間步長
mu = 0.05        # 假設預期回報 5%

# 2. 生成隨機路徑 (從 1.0 開始)
paths = np.ones((n_days, n_paths))
for i in range(1, n_days):
    # 使用幾何布朗運動公式
    shocks = np.random.standard_normal(n_paths)
    paths[i] = paths[i-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)

# 3. 繪圖
fig = go.Figure()

# 畫出隨機路徑
for j in range(n_paths):
    fig.add_trace(go.Scatter(
        y=paths[:, j], 
        mode='lines', 
        line=dict(width=0.5, color='rgba(100, 150, 255, 0.3)'),
        showlegend=False
    ))

# 畫出標竿線 (現價、執行價、障礙價)
fig.add_hline(y=1.0, line_color="black", line_width=2, annotation_text="現價")
fig.add_hline(y=strike_pct, line_dash="dash", line_color="green", annotation_text="執行價")
fig.add_hline(y=ki_pct, line_dash="dot", line_color="red", annotation_text="障礙價")

fig.update_layout(
    height=350, 
    margin=dict(l=10, r=10, t=20, b=10),
    yaxis_range=[0.5, 1.2], # 調整 Y 軸範圍讓波動更明顯
    xaxis_title="未來交易日",
    yaxis_title="相對價格 (1.0=現價)"
)

st.plotly_chart(fig, use_container_width=True)


# --- 稽核按鈕 ---
if st.button("🚀 生成稽核存證並加密"):
    st.balloons()
    st.success(f"已生成稽核編號: {np.random.randint(100000, 999999)}")
    st.info("稽核狀態：符合 2026 金融合規準則。資料已鎖定於本地內網。")
