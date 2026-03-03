import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化中心", layout="wide")

# --- 2. 備援式數據抓取引擎 ---
@st.cache_data(ttl=3600)
def analyze_stock(stock_id):
    """雙引擎抓取並計算五線譜與現價"""
    start_date_dt = datetime.now() - timedelta(days=int(3.5 * 365.25))
    start_date_str = start_date_dt.strftime('%Y-%m-%d')
    
    # A: FinMind
    try:
        TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=TOKEN)
        df = dl.taiwan_stock_daily(stock_id=stock_id.replace(".TW",""), start_date=start_date_str)
        if df is not None and not df.empty:
            df = df.rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')[['Close']]
        else: raise Exception()
    except:
        # B: yfinance 備援
        yf_id = f"{stock_id}.TW" if ".TW" not in stock_id else stock_id
        df = yf.download(yf_id, start=start_date_dt, progress=False, auto_adjust=True)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df[['Close']]
        else: return None

    df = df.sort_index()
    df['t'] = np.arange(len(df))
    slope, intercept = np.polyfit(df['t'], df['Close'], 1)
    df['Trend'] = slope * df['t'] + intercept
    std_dev = (df['Close'] - df['Trend']).std()
    curr_price = float(df['Close'].iloc[-1])
    curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
    
    return {"df": df, "price": curr_price, "sd": curr_sd, "std": std_dev}

# --- 3. 側邊欄：庫存輸入 ---
st.sidebar.header("📋 目前庫存輸入")
shares_675 = st.sidebar.number_input("00675L 股數", value=0, step=1000)
shares_670 = st.sidebar.number_input("00670L 股數", value=0, step=1000)
shares_708 = st.sidebar.number_input("00708L 股數", value=0, step=1000)
current_cash = st.sidebar.number_input("現金餘額 (TWD)", value=500000, step=10000)

# --- 4. 主程式邏輯 ---
st.title("🛡️ 正二量化投資：智慧再平衡監控 (完整五線譜版)")

with st.spinner('同步全球數據中...'):
    res_675 = analyze_stock("00675L")
    res_670 = analyze_stock("00670L")
    res_708 = analyze_stock("00708L")
    vix_df = yf.download("^VIX", period="5d", progress=False)
    vix = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 20.0

if res_675 and res_670 and res_708:
    # A. 計算總資產價值
    val_675 = shares_675 * res_675['price']
    val_670 = shares_670 * res_670['price']
    val_708 = shares_708 * res_708['price']
    total_assets = val_675 + val_670 + val_708 + current_cash
    
    # B. 判定策略權重 (50/20/30)
    sd = res_675['sd']
    if sd >= 2.0: w = {"G": 0.15, "H": 0.10, "B": 0.75}
    elif sd <= -2.0: w = {"G": 0.80, "H": 0.20, "B": 0.00}
    else: w = {"G": 0.50, "H": 0.20, "B": 0.30}
    
    if vix > 30: 
        w["G"] /= 2
        w["B"] = 1 - w["G"] - w["H"]

    # C. 顯示資產現況
    st.subheader(f"💰 總資產估值：{total_assets:,.0f} TWD (VIX: {vix:.1f})")
    
    col_chart, col_action = st.columns([2, 1])
    
    with col_chart:
        st.write("📊 0067