import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化特助", layout="wide")

# --- 2. 核心計算函式 (整合 Token) ---
@st.cache_data(ttl=3600)
def fetch_data_finmind(stock_id, years=3.5):
    """使用 Token 抓取 FinMind 數據"""
    try:
        # 填入您的專屬 Token
        FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=FINMIND_TOKEN) # 執行登入
        
        clean_id = stock_id.replace(".TW", "").replace(".tw", "")
        start_date = (datetime.now() - timedelta(days=int(years * 365.25))).strftime('%Y-%m-%d')
        
        # 抓取台股日成交資料
        df = dl.taiwan_stock_daily(stock_id=clean_id, start_date=start_date)
        
        if df is None or df.empty:
            return None
            
        # 整理欄位格式
        df = df.rename(columns={'date': 'Date', 'close': 'Close'})
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        
        # 線性回歸計算
        df['t'] = np.arange(len(df))
        slope, intercept = np.polyfit(df['t'], df['Close'], 1)
        df['Trend'] = slope * df['t'] + intercept
        
        # 計算標準差位階
        std_dev = (df['Close'] - df['Trend']).std()
        curr_price = float(df['Close'].iloc[-1])
        curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
        
        return {"df": df, "curr_price": curr_price, "curr_sd": curr_sd, "std_dev": std_dev}
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def get_vix_indicator():
    """抓取 VIX 指數 (Yahoo Finance)"""
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        if isinstance(vix_data.columns, pd.MultiIndex):
            vix_data.columns = vix_data.columns.get_level_values(0)
        return float(vix_data['Close'].iloc[-1])
    except:
        return 20.0

def get_target_weights(sd_level, vix):
    """50/20/30 核心策略邏輯"""
    if sd_level >= 2.0:      # 樂觀線
        w = {"Growth": 0.15, "Harvest": 0.10, "Buffer": 0.75}
    elif sd_level <= -2.0:   # 悲觀線
        w = {"Growth": 0.80, "Harvest": 0.20, "Buffer": 0.00}
    else:                    # 趨勢線 (基準配置)
        w = {"Growth": 0.50, "Harvest": 0.20, "Buffer": 0.30}
    
    if vix > 30:
        cut = w["Growth"] * 0.5
        w["Growth"] -= cut
        w["Buffer"] += cut
    return w

# --- 3. 主介面呈現 ---
st.title("🛡️ 正二槓桿量化監控 (系統穩定營運中)")
st.sidebar.info(f"策略基準：3.5 年線性回歸\n更新時間：{datetime.now().strftime('%H:%M:%S')}")

total_assets = st.sidebar.number_input("總投入資金 (TWD)", value=1000000, step=100000)

try:
    vix = get_vix_indicator()
    with st.spinner('連線至 FinMind 資料庫...'):
        tw_equity = fetch_data_finmind("00675L")
        us_equity = fetch_data_finmind("00670L")
        gold_2x = fetch_data_finmind("00708L")

    if tw_equity and us_equity and gold_2x:
        weights = get_target_weights(tw_equity['curr_sd'], vix)
        
        # 頂部數據列
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("00675L 位階", f"{tw_equity['curr_sd']:.2f} SD")
        c2.metric("VIX 指數", f"{vix:.2f}")
        c3.metric("00670L 現價", f"{us_equity['curr_price']:.1f}")
        c4.metric("00708L 現價", f"{gold_2x['curr_price']:.1f}")

        # 繪製五線譜
        st.subheader("📊 00675L 趨勢位階圖")
        df_p = tw_equity['df']
        sd = tw_equity['std_dev']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格", line=dict(color='black')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢線", line=dict(color='gray', dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*sd, name="樂觀(+2SD)", line=dict(color='red')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*sd, name="悲觀(-2SD)", line=dict(color='green')))
        st.plotly_chart(fig, use_container_width=True)

        # 再平衡表格
        st.subheader("🛠️ 本日配置建議")
        g_each = (total_assets * weights['Growth']) / 2
        re_df = pd.DataFrame([
            {"項目": "成長桶 - 00675L (台)", "權重": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{g_each:,.0f}"},
            {"項目": "成長桶 - 00670L (美)", "權重": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{g_each:,.0f}"},
            {"項目": "波動桶 - 00708L (金)", "權重": f"{weights['Harvest']*100:.1f}%", "目標金額": f"{total_assets * weights['Harvest']:,.0f}"},
            {"項目": "儲備現金", "權重": f"{weights['Buffer']*100:.1f}%", "目標金額": f"{total_assets * weights['Buffer']:,.0f}"}
        ])
        st.table(re_df)
    else:
        st.warning("⚠️ 數據抓取中，請稍候。若持續未出現資料，請檢查 FinMind Token 狀態。")

except Exception as e:
    st.error(f"系統錯誤：{e}")