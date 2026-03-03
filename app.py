import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化特助", layout="wide")

# --- 2. 核心計算函式 ---
@st.cache_data(ttl=3600)
def fetch_data_and_analyze(symbol, years=3.5):
    """抓取數據並計算 3.5 年樂活五線譜"""
    if ".TW" not in symbol and symbol.isdigit():
        symbol = f"{symbol}.TW"
            
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(years * 365.25))
    
    # 嘗試抓取數據，加入 auto_adjust 確保格式正確
    df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=True)
    
    # 檢查數據是否為空
    if df is None or len(df) < 10: # 至少要有10筆資料才能計算
        return None
    
    # 修正 yfinance 可能回傳的多層索引問題
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 確保抓到的是 Close 價格
    price_col = 'Close' if 'Close' in df.columns else df.columns[0]
    df = df[[price_col]].dropna()
    
    df['t'] = np.arange(len(df))
    
    # 線性回歸 (趨勢線)
    slope, intercept = np.polyfit(df['t'], df[price_col], 1)
    df['Trend'] = slope * df['t'] + intercept
    
    # 標準差與位階
    std_dev = (df[price_col] - df['Trend']).std()
    curr_price = float(df[price_col].iloc[-1]) # 這裡就是報錯的地方，現在加了長度檢查
    curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
    
    return {"df": df, "curr_price": curr_price, "curr_sd": curr_sd, "std_dev": std_dev, "price_col": price_col}

@st.cache_data(ttl=3600)
def get_vix_indicator():
    """抓取 VIX 指數"""
    vix_data = yf.download("^VIX", period="5d", auto_adjust=True)
    if vix_data.empty:
        return 20.0 # 若抓不到則給予預設基準值
    return float(vix_data['Close'].iloc[-1] if 'Close' in vix_data.columns else vix_data.iloc[-1,0])

# --- 3. 策略權重邏輯 (維持不變) ---
def get_target_weights(sd_level, vix):
    if sd_level >= 2.0:      
        w = {"Growth": 0.15, "Harvest": 0.10, "Buffer": 0.75}
    elif sd_level <= -2.0:   
        w = {"Growth": 0.80, "Harvest": 0.20, "Buffer": 0.00}
    else:                    
        w = {"Growth": 0.50, "Harvest": 0.20, "Buffer": 0.30}
    if vix > 30:
        cut = w["Growth"] * 0.5
        w["Growth"] -= cut
        w["Buffer"] += cut
    return w

# --- 4. 主介面邏輯 ---
st.title("🛡️ 正二槓桿：量化科學投資監控")
st.sidebar.header("🏦 資產配置中心 (TWD)")
total_assets = st.sidebar.number_input("當前可投入總資金", value=1000000, step=100000)

try:
    vix = get_vix_indicator()
    
    # 依序檢查數據
    with st.spinner('正在與市場同步數據...'):
        tw_equity = fetch_data_and_analyze("00675L")
        us_equity = fetch_data_and_analyze("00670L")
        gold_2x = fetch_data_and_analyze("00708L")

    if tw_equity and us_equity and gold_2x:
        # 顯示指標與繪圖 (邏輯同前，略縮...)
        weights = get_target_weights(tw_equity['curr_sd'], vix)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("00675L 位階", f"{tw_equity['curr_sd']:.2f} SD")
        c2.metric("VIX 恐慌指數", f"{vix:.2f}")
        c3.metric("00670L 現價", f"{us_equity['curr_price']:.2f}")
        c4.metric("00708L 現價", f"{gold_2x['curr_price']:.2f}")

        # 繪圖
        df_p = tw_equity['df']
        sd = tw_equity['std_dev']
        col = tw_equity['price_col']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p[col], name="價格", line=dict(color='black')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢線", line=dict(color='gray', dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*sd, name="樂觀線(+2SD)", line=dict(color='red')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*sd, name="悲觀線(-2SD)", line=dict(color='green')))
        st.plotly_chart(fig, use_container_width=True)

        # 顯示再平衡表格
        growth_each = (total_assets * weights['Growth']) / 2
        rebalance_table = [
            {"項目": "台股正二 (00675L)", "比例": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{growth_each:,.0f}"},
            {"項目": "美股正二 (00670L)", "比例": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{growth_each:,.0f}"},
            {"項目": "黃金正二 (00708L)", "比例": f"{weights['Harvest']*100:.1f}%", "目標金額": f"{total_assets * weights['Harvest']:,.0f}"},
            {"項目": "儲備現金", "比例": f"{weights['Buffer']*100:.1f}%", "目標金額": f"{total_assets * weights['Buffer']:,.0f}"}
        ]
        st.table(pd.DataFrame(rebalance_table))
    else:
        st.error("⚠️ 目前無法從伺服器獲取完整數據。請檢查：1. 是否為開盤時段網路壅塞？ 2. Yahoo Finance 是否暫時斷線？ 請稍後 5 分鐘再重新整頁面。")

except Exception as e:
    st.error(f"系統執行異常: {e}")
