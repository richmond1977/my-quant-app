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
def get_data_engine(stock_id, years=3.5):
    """雙引擎抓取：FinMind 優先，yfinance 備援"""
    start_date_str = (datetime.now() - timedelta(days=int(years * 365.25))).strftime('%Y-%m-%d')
    start_date_dt = datetime.now() - timedelta(days=int(years * 365.25))
    
    # 嘗試方案 A: FinMind
    try:
        TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=TOKEN)
        df = dl.taiwan_stock_daily(stock_id=stock_id.replace(".TW",""), start_date=start_date_str)
        if df is not None and not df.empty:
            df = df.rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')[['Close']]
            return df, "FinMind"
    except:
        pass

    # 嘗試方案 B: yfinance (備援)
    try:
        yf_id = f"{stock_id}.TW" if ".TW" not in stock_id else stock_id
        df_yf = yf.download(yf_id, start=start_date_dt, progress=False, auto_adjust=True)
        if not df_yf.empty:
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.get_level_values(0)
            df_yf = df_yf[['Close']].rename(columns={'Close': 'Close'})
            return df_yf, "yfinance"
    except:
        pass
        
    return None, None

@st.cache_data(ttl=3600)
def analyze_stock(stock_id):
    df, source = get_data_engine(stock_id)
    if df is None: return None
    
    df = df.sort_index()
    df['t'] = np.arange(len(df))
    slope, intercept = np.polyfit(df['t'], df['Close'], 1)
    df['Trend'] = slope * df['t'] + intercept
    std_dev = (df['Close'] - df['Trend']).std()
    
    curr_price = float(df['Close'].iloc[-1])
    curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
    return {"df": df, "price": curr_price, "sd": curr_sd, "std": std_dev, "src": source}

# --- 3. 介面與策略 ---
st.title("🛡️ 正二量化投資監控 (雙引擎版)")
assets = st.sidebar.number_input("總資金 (TWD)", value=1000000)

with st.spinner('連線中...'):
    res_675 = analyze_stock("00675L")
    res_670 = analyze_stock("00670L")
    res_708 = analyze_stock("00708L")
    vix_df = yf.download("^VIX", period="1d", progress=False)
    vix = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 20.0

if res_675 and res_670 and res_708:
    # 策略計算
    sd = res_675['sd']
    if sd >= 2.0: w = {"G": 0.15, "H": 0.10, "B": 0.75}
    elif sd <= -2.0: w = {"G": 0.80, "H": 0.20, "B": 0.00}
    else: w = {"G": 0.50, "H": 0.20, "B": 0.30}
    
    if vix > 30: w["G"] /= 2; w["B"] = 1 - w["G"] - w["H"]

    # 顯示
    st.write(f"📡 數據來源: {res_675['src']} | VIX: {vix:.1f}")
    c1, c2, c3 = st.columns(3)
    c1.metric("00675L 位階", f"{sd:.2f} SD")
    c2.metric("00670L 現價", f"{res_670['price']:.1f}")
    c3.metric("00708L 現價", f"{res_708['price']:.1f}")

    # 圖表
    df_p = res_675['df']
    s = res_675['std']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格"))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢", line=dict(dash='dot')))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*s, name="+2SD", line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*s, name="-2SD", line=dict(color='green')))
    st.plotly_chart(fig, use_container_width=True)

    # 建議表
    st.table(pd.DataFrame([
        {"標的": "台正2 (00675L)", "目標金額": f"{assets*w['G']/2:,.0f}"},
        {"標的": "美正2 (00670L)", "目標金額": f"{assets*w['G']/2:,.0f}"},
        {"標的": "金正2 (00708L)", "目標金額": f"{assets*w['H']:,.0f}"},
        {"標的": "儲備現金", "目標金額": f"{assets*w['B']:,.0f}"},
    ]))
else:
    st.error("❌ 所有引擎皆抓取失敗。請檢查網路或稍後再試。")