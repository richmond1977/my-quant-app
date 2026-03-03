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
@st.cache_data(ttl=600) # 縮短快取時間，方便偵錯
def analyze_stock(stock_id):
    try:
        TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wMyAxOTowNzoxNCIsInVzZXJfaWQiOiJyaWNobW9uZDE5NzciLCJlbWFpbCI6InlhbmcucmljaG1vbmRAZ21haWwuY29tIiwiaXAiOiIxMjMuMjQwLjk5LjgzIn0.I_YG7YMDHwXUThwYV8un6BxTz0YQIkjlctaRWuhv_1M"
        dl = DataLoader()
        dl.login(token=TOKEN)
        
        # 抓取 3.5 年資料
        start_date = (datetime.now() - timedelta(days=int(3.5 * 365))).strftime('%Y-%m-%d')
        df = dl.taiwan_stock_daily(stock_id=stock_id.replace(".TW",""), start_date=start_date)
        
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date').sort_index()
            
            # 數據完整性判斷：至少要有 200 天以上的資料
            if len(df) < 10:
                st.warning(f"⚠️ {stock_id} 數據量不足 (僅 {len(df)} 筆)，請確認代碼是否正確。")
                return None
            
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
        st.error(f"解析 {stock_id} 時發生異常: {e}")
        return None

# --- 3. 側邊欄與 VIX ---
st.sidebar.header("📋 庫存輸入")
s675 = st.sidebar.number_input("00675L 股數", value=0, step=1000)
s670 = st.sidebar.number_input("00670L 股數", value=0, step=1000)
s708 = st.sidebar.number_input("00708L 股數", value=0, step=1000)
cash = st.sidebar.number_input("現金 (TWD)", value=0, step=10000)

vix = 20.0
try:
    v_df = yf.download("^VIX", period="1d", progress=False)
    if not v_df.empty:
        if isinstance(v_df.columns, pd.MultiIndex): v_df.columns = v_df.columns.get_level_values(0)
        vix = float(v_df['Close'].iloc[-1])
except: pass

# --- 4. 主程式 ---
st.title("🛡️ 正二量化投資監控中心")

with st.spinner('連線資料庫中...'):
    res_675 = analyze_stock("00675L")
    res_670 = analyze_stock("00670L")
    res_708 = analyze_stock("00708L")

if res_675 and res_670 and res_708:
    # 權重與計算
    total = (s675 * res_675['price']) + (s670 * res_670['price']) + (s708 * res_708['price']) + cash
    sd = res_675['sd']
    
    # 50/20/30 策略
    if sd >= 2.0: w = {"G": 15, "H": 10, "B": 75}
    elif sd <= -2.0: w = {"G": 80, "H": 20, "B": 0}
    else: w = {"G": 50, "H": 20, "B": 30}
    
    if vix > 30: w["G"] /= 2; w["B"] = 100 - w["G"] - w["H"]

    st.info(f"📅 數據同步至：{res_675['date']} | VIX: {vix:.1f}")
    st.subheader(f"💰 總資產：{total:,.0f} TWD")

    l, r = st.columns([1.8, 1.2])
    with l:
        df_p = res_675['df']
        s = res_675['std']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格", line=dict(color='black')))
        for i, color, name in [(2, 'red', '+2SD'), (1, 'orange', '+1SD'), (0, 'gray', 'Trend'), (-1, 'lightgreen', '-1SD'), (-2, 'green', '-2SD')]:
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+i*s, name=name, line=dict(color=color, dash='dash' if i!=0 else 'solid')))
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("00675L", f"{res_675['price']:.2f}")
        c2.metric("00670L", f"{res_670['price']:.2f}")
        c3.metric("00708L", f"{res_708['price']:.2f}")

    with r:
        st.write("🛠️ 再平衡建議")
        def mk_row(n, curr_s, p, t_p, tot):
            curr_v = curr_s * p
            t_v = tot * (t_p / 100)
            diff = (t_v - curr_v) / p
            return {"標的": n, "市值": f"{curr_v:,.0f}", "目前%": f"{(curr_v/tot*100 if tot>0 else 0):.1f}%", "建議%": f"{t_p:.1f}%", "調整股數": f"{int(diff):,}"}
        
        rows = [
            mk_row("00675L", s675, res_675['price'], w['G']/2, total),
            mk_row("00670L", s670, res_670['price'], w['G']/2, total),
            mk_row("00708L", s708, res_708['price'], w['H'], total),
            {"標的": "現金", "市值": f"{cash:,.0f}", "目前%": f"{(cash/total*100 if total>0 else 0):.1f}%", "建議%": f"{w['B']:.1f}%", "調整股數": "-"}
        ]
        st.table(pd.DataFrame(rows))
        st.write(f"📈 位階標註: {sd:.2f} SD")

else:
    st.error("❌ 仍無法抓取完整市場數據。")
    st.info("💡 特助偵錯建議：請確認 GitHub 中的 `requirements.txt` 是否包含 `FinMind` 與 `yfinance`。若今日是假日或台股休市，部分 API 可能回傳空值。")
