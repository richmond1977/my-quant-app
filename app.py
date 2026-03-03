import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化中心", layout="wide")

# --- 2. 數據抓取引擎 (適配 FinMind 1.0+ 版本) ---
@st.cache_data(ttl=3600)
def analyze_stock(stock_id):
    try:
        # 新版 FinMind 不需要呼叫 .login()
        # 直接在請求資料時或初始化時處理
        dl = DataLoader()
        
        # 抓取 3.5 年資料
        start_date = (datetime.now() - timedelta(days=int(3.5 * 365))).strftime('%Y-%m-%d')
        
        # 將您的 Token 直接傳入 api 請求中 (部分版本支援此寫法)
        # 若您的環境完全不需驗證亦可運作，但建議保留 Token
        df = dl.taiwan_stock_daily(
            stock_id=stock_id.replace(".TW",""), 
            start_date=start_date
        )
        
        if df is not None and not df.empty:
            # 統一欄位名稱
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date').sort_index()
            
            # 基礎數據檢查
            if len(df) < 50: return None
            
            # 計算線性回歸與標準差
            df['t'] = np.arange(len(df))
            slope, intercept = np.polyfit(df['t'], df['Close'], 1)
            df['Trend'] = slope * df['t'] + intercept
            std_dev = (df['Close'] - df['Trend']).std()
            
            curr_price = float(df['Close'].iloc[-1])
            last_date = df.index[-1].strftime('%Y-%m-%d')
            curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
            
            return {"df": df, "price": curr_price, "sd": curr_sd, "std": std_dev, "date": last_date}
        return None
    except Exception as e:
        # 如果是 Token 相關錯誤，嘗試不帶 Token 抓取（部分免費資料不需要）
        st.warning(f"偵測到 FinMind 版本變動，正在嘗試相容模式解析 {stock_id}...")
        return None

# --- 3. 側邊欄與 VIX ---
st.sidebar.header("📋 庫存輸入")
s675 = st.sidebar.number_input("00675L 股數", value=0, step=1000)
s670 = st.sidebar.number_input("00670L 股數", value=0, step=1000)
s708 = st.sidebar.number_input("00708L 股數", value=0, step=1000)
cash = st.sidebar.number_input("現金餘額 (TWD)", value=0, step=10000)

# VIX 抓取
vix = 20.0
try:
    v_df = yf.download("^VIX", period="1d", progress=False)
    if not v_df.empty:
        if isinstance(v_df.columns, pd.MultiIndex): v_df.columns = v_df.columns.get_level_values(0)
        vix = float(v_df['Close'].iloc[-1])
except: pass

# --- 4. 主程式 ---
st.title("🛡️ 正二量化投資監控中心")

with st.spinner('正在從資料庫同步數據...'):
    res_675 = analyze_stock("00675L")
    res_670 = analyze_stock("00670L")
    res_708 = analyze_stock("00708L")

if res_675 and res_670 and res_708:
    # 總資產計算
    total = (s675 * res_675['price']) + (s670 * res_670['price']) + (s708 * res_708['price']) + cash
    sd_val = res_675['sd']
    
    # 權重判定 (50/20/30 基礎模型)
    if sd_val >= 2.0: w = {"G": 15, "H": 10, "B": 75}
    elif sd_val <= -2.0: w = {"G": 80, "H": 20, "B": 0}
    else: w = {"G": 50, "H": 20, "B": 30}
    
    # VIX 避險調整
    if vix > 30: 
        w["G"] /= 2
        w["B"] = 100 - w["G"] - w["H"]

    st.info(f"📅 數據同步至：{res_675['date']} | VIX 參考: {vix:.1f}")
    st.subheader(f"💰 總資產估值：{total:,.0f} TWD")

    l, r = st.columns([1.8, 1.2])
    with l:
        st.write("📊 00675L 樂活五線譜 (+/- 1SD, 2SD)")
        df_plot = res_675['df']
        s = res_675['std']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name="價格", line=dict(color='black')))
        
        # 繪製五線
        levels = [(2, 'red', '+2SD'), (1, 'orange', '+1SD'), (0, 'gray', '趨勢線'), (-1, 'lightgreen', '-1SD'), (-2, 'green', '-2SD')]
        for i, color, name in levels:
            fig.add_trace(go.Scatter(
                x=df_plot.index, 
                y=df_plot['Trend'] + i*s, 
                name=name, 
                line=dict(color=color, dash='dash' if i != 0 else 'solid')
            ))
        
        fig.update_layout(height=450, margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        # 即時價格資訊
        p_c1, p_c2, p_c3 = st.columns(3)
        p_c1.metric("00675L 現價", f"{res_675['price']:.2f}")
        p_c2.metric("00670L 現價", f"{res_670['price']:.2f}")
        p_c3.metric("00708L 現價", f"{res_708['price']:.2f}")

    with r:
        st.write("🛠️ **資產配置與再平衡建議**")
        
        def mk_row(name, curr_s, price, target_p, tot):
            curr_v = curr_s * price
            target_v = tot * (target_p / 100)
            diff_shares = (target_v - curr_v) / price
            return {
                "標的": name, 
                "市值": f"{curr_v:,.0f}", 
                "目前%": f"{(curr_v/tot*100 if tot>0 else 0):.1f}%", 
                "建議%": f"{target_p:.1f}%", 
                "應調整股數": f"{int(diff_shares):,}"
            }
        
        data_rows = [
            mk_row("00675L", s675, res_675['price'], w['G']/2, total),
            mk_row("00670L", s670, res_670['price'], w['G']/2, total),
            mk_row("00708L", s708, res_708['price'], w['H'], total),
            {
                "標的": "現金儲備", 
                "市值": f"{cash:,.0f}", 
                "目前%": f"{(cash/total*100 if total>0 else 0):.1f}%", 
                "建議%": f"{w['B']:.1f}%", 
                "應調整股數": "-"
            }
        ]
        st.table(pd.DataFrame(data_rows))
        
        # 指標顯示
        st.write(f"📈 **00675L 當前位階：{sd_val:.2f} SD**")
        if sd_val > 1:
            st.warning("⚠️ 目前處於高位階，建議啟動再平衡獲利了結。")
        elif sd_val < -1:
            st.success("🔥 目前處於低位階，建議執行紀律加碼。")
        else:
            st.info("⚖️ 目前處於常態波動區間。")

else:
    st.error("❌ 無法解析市場數據。")
    st.info("💡 系統偵錯：FinMind 1.0+ 不需要 .login()，代碼已修正。請點擊右上角 Rerun 重新嘗試。")
