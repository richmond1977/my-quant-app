import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化中心", layout="wide")

# --- 2. 數據抓取引擎 ---
@st.cache_data(ttl=3600)
def analyze_stock(stock_id):
    """專攻 FinMind 抓取，徹底避開 yfinance 的 Rate Limit 問題"""
    start_date_dt = datetime.now() - timedelta(days=int(3.5 * 365.25))
    start_date_str = start_date_dt.strftime('%Y-%m-%d')
    
    try:
        TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=TOKEN)
        
        # 00675L, 00670L, 00708L 都是台股代碼，FinMind 支援極佳
        df = dl.taiwan_stock_daily(stock_id=stock_id.replace(".TW",""), start_date=start_date_str)
        
        if df is not None and not df.empty:
            # FinMind 回傳的原始欄位通常是小寫，強制轉換確保一致性
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date').sort_index()
            
            # 計算統計指標
            df['t'] = np.arange(len(df))
            if len(df) < 50: return None
            
            slope, intercept = np.polyfit(df['t'], df['Close'], 1)
            df['Trend'] = slope * df['t'] + intercept
            std_dev = (df['Close'] - df['Trend']).std()
            curr_price = float(df['Close'].iloc[-1])
            curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
            
            return {"df": df, "price": curr_price, "sd": curr_sd, "std": std_dev}
        else:
            return None
    except Exception as e:
        # 在日誌中列印錯誤但不中斷程式
        print(f"FinMind Error for {stock_id}: {e}")
        return None

# --- 3. 側邊欄 ---
st.sidebar.header("📋 目前庫存輸入")
shares_675 = st.sidebar.number_input("00675L 股數", value=0, step=1000)
shares_670 = st.sidebar.number_input("00670L 股數", value=0, step=1000)
shares_708 = st.sidebar.number_input("00708L 股數", value=0, step=1000)
current_cash = st.sidebar.number_input("現金餘額 (TWD)", value=0, step=10000)

# --- 4. 主程式邏輯 ---
st.title("🛡️ 正二量化投資：再平衡監控中心")

with st.spinner('正在透過 FinMind 獲取最新行情...'):
    res_675 = analyze_stock("00675L")
    res_670 = analyze_stock("00670L")
    res_708 = analyze_stock("00708L")
    
    # VIX 抓取失敗時提供預設值 20.0
    try:
        vix_df = yf.download("^VIX", period="1d", progress=False)
        vix = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 20.0
    except:
        vix = 20.0

# 顯示介面
if res_675 and res_670 and res_708:
    val_675 = shares_675 * res_675['price']
    val_670 = shares_670 * res_670['price']
    val_708 = shares_708 * res_708['price']
    total_assets = val_675 + val_670 + val_708 + current_cash
    
    sd = res_675['sd']
    if sd >= 2.0: w = {"G": 0.15, "H": 0.10, "B": 0.75}
    elif sd <= -2.0: w = {"G": 0.80, "H": 0.20, "B": 0.00}
    else: w = {"G": 0.50, "H": 0.20, "B": 0.30}
    
    if vix > 30: 
        w["G"] /= 2
        w["B"] = 1 - w["G"] - w["H"]

    st.subheader(f"💰 總資產估值：{total_assets:,.0f} TWD (VIX: {vix:.1f})")
    
    col_l, col_r = st.columns([1.8, 1.2])
    
    with col_l:
        st.write("📊 00675L 樂活五線譜")
        df_p = res_675['df']
        s = res_675['std']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格", line=dict(color='black')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*s, name="+2SD", line=dict(color='red', dash='dash')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+1*s, name="+1SD", line=dict(color='orange', dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢"))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-1*s, name="-1SD", line=dict(color='lightgreen', dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*s, name="-2SD", line=dict(color='green', dash='dash')))
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        # 價格區
        p_c1, p_c2, p_c3 = st.columns(3)
        p_c1.metric("00675L", f"{res_675['price']:.2f}")
        p_c2.metric("00670L", f"{res_670['price']:.2f}")
        p_c3.metric("00708L", f"{res_708['price']:.2f}")

    with col_r:
        st.write("🛠️ **資產配置總表**")
        def calc_row(name, curr_v, target_p, price, total):
            target_v = total * (target_p / 100)
            diff = target_v - curr_v
            curr_p = (curr_v / total * 100) if total > 0 else 0
            shares = diff / price if price > 0 else 0
            return {"標的": name, "市值": f"{curr_v:,.0f}", "目前%": f"{curr_p:.1f}%", "建議%": f"{target_p:.1f}%", "調整股數": f"{int(shares):,}"}

        rows = [
            calc_row("00675L", val_675, (w['G']/2)*100, res_675['price'], total_assets),
            calc_row("00670L", val_670, (w['G']/2)*100, res_670['price'], total_assets),
            calc_row("00708L", val_708, w['H']*100, res_708['price'], total_assets),
            {"標的": "現金", "市值": f"{current_cash:,.0f}", "目前%": f"{(current_cash/total_assets*100):.1f}%", "建議%": f"{w['B']*100:.1f}%", "調整股數": "-"}
        ]
        st.table(pd.DataFrame(rows))
        
        st.info(f"00675L 位階: {sd:.2f} SD")
        if sd > 1.5: st.error("建議獲利了結")
        elif sd < -1.5: st.success("建議加碼進場")
else:
    st.error("❌ 數據解析失敗。原因可能是 FinMind API 暫時性忙碌。")
    st.info("💡 解決建議：請點擊右上角 Rerun，或檢查您的 Token 是否仍有效（2026-03-03 仍可使用）。")
