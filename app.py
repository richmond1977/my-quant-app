import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化中心", layout="wide")

# --- 2. 數據抓取引擎 (強化容錯邏輯) ---
@st.cache_data(ttl=3600)
def analyze_stock(stock_id):
    """整合 FinMind Token 與 yfinance 備援"""
    start_date_dt = datetime.now() - timedelta(days=int(3.5 * 365.25))
    start_date_str = start_date_dt.strftime('%Y-%m-%d')
    
    # 嘗試 A: FinMind (優先)
    try:
        TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=TOKEN)
        df = dl.taiwan_stock_daily(stock_id=stock_id.replace(".TW",""), start_date=start_date_str)
        
        if df is not None and not df.empty:
            df = df.rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')[['Close']]
        else:
            raise Exception("FinMind empty")
    except:
        # 嘗試 B: yfinance (備援)
        try:
            yf_id = f"{stock_id}.TW" if stock_id.isdigit() else stock_id
            df_yf = yf.download(yf_id, start=start_date_dt, progress=False, auto_adjust=True)
            if not df_yf.empty:
                # 處理 yfinance 可能的多層表頭
                if isinstance(df_yf.columns, pd.MultiIndex):
                    df_yf.columns = df_yf.columns.get_level_values(0)
                df = df_yf[['Close']]
            else:
                return None
        except:
            return None

    # 計算統計指標
    df = df.sort_index()
    df['t'] = np.arange(len(df))
    # 避免數據太少導致回歸錯誤
    if len(df) < 100: return None
    
    slope, intercept = np.polyfit(df['t'], df['Close'], 1)
    df['Trend'] = slope * df['t'] + intercept
    std_dev = (df['Close'] - df['Trend']).std()
    curr_price = float(df['Close'].iloc[-1])
    curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
    
    return {"df": df, "price": curr_price, "sd": curr_sd, "std": std_dev}

# --- 3. 側邊欄 ---
st.sidebar.header("📋 目前庫存輸入")
shares_675 = st.sidebar.number_input("00675L 股數", value=0, step=1000)
shares_670 = st.sidebar.number_input("00670L 股數", value=0, step=1000)
shares_708 = st.sidebar.number_input("00708L 股數", value=0, step=1000)
current_cash = st.sidebar.number_input("現金餘額 (TWD)", value=0, step=10000)

# --- 4. 主程式邏輯 ---
st.title("🛡️ 正二量化投資：再平衡監控中心")

with st.spinner('同步市場數據中，請稍候...'):
    res_675 = analyze_stock("00675L")
    res_670 = analyze_stock("00670L")
    res_708 = analyze_stock("00708L")
    # VIX 抓取
    vix_df = yf.download("^VIX", period="5d", progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex): vix_df.columns = vix_df.columns.get_level_values(0)
    vix = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 20.0

# 只有當三大標的都抓到資料才顯示
if res_675 and res_670 and res_708:
    # A. 計算市值與總資產
    val_675 = shares_675 * res_675['price']
    val_670 = shares_670 * res_670['price']
    val_708 = shares_708 * res_708['price']
    total_assets = val_675 + val_670 + val_708 + current_cash
    
    # B. 權重判定邏輯
    sd = res_675['sd']
    if sd >= 2.0: w = {"G": 0.15, "H": 0.10, "B": 0.75}
    elif sd <= -2.0: w = {"G": 0.80, "H": 0.20, "B": 0.00}
    else: w = {"G": 0.50, "H": 0.20, "B": 0.30}
    
    if vix > 30: 
        w["G"] /= 2
        w["B"] = 1 - w["G"] - w["H"]

    st.subheader(f"💰 總資產估值：{total_assets:,.0f} TWD (VIX: {vix:.1f})")
    
    col_left, col_right = st.columns([1.8, 1.2])
    
    with col_left:
        st.write("📊 00675L 樂活五線譜")
        df_p = res_675['df']
        s = res_675['std']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格", line=dict(color='black', width=1.5)))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*s, name="+2SD", line=dict(color='red', width=1, dash='dash')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+1*s, name="+1SD", line=dict(color='orange', width=1, dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢", line=dict(color='gray', width=1)))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-1*s, name="-1SD", line=dict(color='lightgreen', width=1, dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*s, name="-2SD", line=dict(color='green', width=1, dash='dash')))
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

        st.write("📌 **標的目前價格**")
        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.metric("00675L", f"{res_675['price']:.2f}")
        p_col2.metric("00670L", f"{res_670['price']:.2f}")
        p_col3.metric("00708L", f"{res_708['price']:.2f}")

    with col_right:
        st.write("🛠️ **資產配置與再平衡總表**")
        
        def calculate_row(name, curr_val, target_pct, price, total):
            target_val = total * (target_pct / 100)
            diff_val = target_val - curr_val
            curr_pct = (curr_val / total * 100) if total > 0 else 0
            shares = diff_val / price if price > 0 else 0
            return {
                "標的": name,
                "市值": f"{curr_val:,.0f}",
                "目前占比": f"{curr_pct:.1f}%",
                "建議占比": f"{target_pct:.1f}%",
                "應增減股數": f"{int(shares):,}"
            }

        rows = [
            calculate_row("00675L", val_675, (w['G']/2)*100, res_675['price'], total_assets),
            calculate_row("00670L", val_670, (w['G']/2)*100, res_670['price'], total_assets),
            calculate_row("00708L", val_708, w['H']*100, res_708['price'], total_assets)
        ]
        
        cash_pct = (current_cash / total_assets * 100) if total_assets > 0 else 0
        rows.append({
            "標的": "現金儲備",
            "市值": f"{current_cash:,.0f}",
            "目前占比": f"{cash_pct:.1f}%",
            "建議占比": f"{w['B']*100:.1f}%",
            "應增減股數": "-"
        })
        
        st.table(pd.DataFrame(rows))
        
        if sd > 1.5: st.error(f"⚠️ 位階極高 ({sd:.2f})：建議獲利了結")
        elif sd < -1.5: st.success(f"🔥 位階極低 ({sd:.2f})：建議加碼進場")
        else: st.info(f"⚖️ 位階平衡 ({sd:.2f})")

else:
    st.error("❌ 數據抓取失敗：請檢查網路或稍後點擊右上角 Rerun。")
    st.info("💡 提示：若 FinMind Token 流量受限，系統會自動切換 yfinance，請確保 requirements.txt 包含這兩個套件。")
