import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化特助", layout="wide")

# --- 2. 核心計算函式 (偵錯與相容性強化版) ---
@st.cache_data(ttl=3600)
def fetch_data_finmind(stock_id, years=3.5):
    """強化版數據抓取：支援 Token 登入與欄位自動校正"""
    try:
        # 您的 Token
        FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=FINMIND_TOKEN)
        
        clean_id = stock_id.replace(".TW", "").replace(".tw", "")
        start_date = (datetime.now() - timedelta(days=int(years * 365.25))).strftime('%Y-%m-%d')
        
        # 抓取資料
        df = dl.taiwan_stock_daily(stock_id=clean_id, start_date=start_date)
        
        if df is None or df.empty:
            st.error(f"標的 {clean_id} 回傳數據為空，請確認 FinMind 權限。")
            return None
            
        # 自動識別日期與收盤價欄位 (不論大小寫)
        df.columns = [c.lower() for c in df.columns]
        if 'date' in df.columns:
            df = df.rename(columns={'date': 'Date'})
        if 'close' in df.columns:
            df = df.rename(columns={'close': 'Close'})
        
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        
        # 計算線性回歸
        df['t'] = np.arange(len(df))
        slope, intercept = np.polyfit(df['t'], df['Close'], 1)
        df['Trend'] = slope * df['t'] + intercept
        
        std_dev = (df['Close'] - df['Trend']).std()
        curr_price = float(df['Close'].iloc[-1])
        curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
        
        return {"df": df, "curr_price": curr_price, "curr_sd": curr_sd, "std_dev": std_dev}
    except Exception as e:
        st.warning(f"解析 {stock_id} 時發生錯誤: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def get_vix_indicator():
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        if isinstance(vix_data.columns, pd.MultiIndex):
            vix_data.columns = vix_data.columns.get_level_values(0)
        return float(vix_data['Close'].iloc[-1])
    except:
        return 20.0

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

# --- 3. 主介面 ---
st.title("🛡️ 正二槓桿量化監控中心")
total_assets = st.sidebar.number_input("總投入資金 (TWD)", value=1000000, step=100000)

vix = get_vix_indicator()

with st.spinner('正在同步市場數據...'):
    # 執行抓取
    tw_equity = fetch_data_finmind("00675L")
    us_equity = fetch_data_finmind("00670L")
    gold_2x = fetch_data_finmind("00708L")

# 判斷是否顯示
if tw_equity and us_equity and gold_2x:
    weights = get_target_weights(tw_equity['curr_sd'], vix)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("00675L 位階", f"{tw_equity['curr_sd']:.2f} SD")
    c2.metric("VIX 指數", f"{vix:.2f}")
    c3.metric("00670L 現價", f"{us_equity['curr_price']:.1f}")
    c4.metric("00708L 現價", f"{gold_2x['curr_price']:.1f}")

    # 圖表
    df_p = tw_equity['df']
    sd = tw_equity['std_dev']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格", line=dict(color='black')))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢線", line=dict(color='gray', dash='dot')))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*sd, name="樂觀", line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*sd, name="悲觀", line=dict(color='green')))
    st.plotly_chart(fig, use_container_width=True)

    # 指令表
    g_each = (total_assets * weights['Growth']) / 2
    st.table(pd.DataFrame([
        {"項目": "00675L (台正2)", "佔比": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{g_each:,.0f}"},
        {"項目": "00670L (美正2)", "佔比": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{g_each:,.0f}"},
        {"項目": "00708L (金正2)", "佔比": f"{weights['Harvest']*100:.1f}%", "目標金額": f"{total_assets * weights['Harvest']:,.0f}"},
        {"項目": "儲備現金", "佔比": f"{weights['Buffer']*100:.1f}%", "目標金額": f"{total_assets * weights['Buffer']:,.0f}"}
    ]))
else:
    st.warning("⚠️ 數據未能成功載入。")
    if not tw_equity: st.info("提示：00675L 抓取失敗")
    if not us_equity: st.info("提示：00670L 抓取失敗")
    if not gold_2x: st.info("提示：00708L 抓取失敗")