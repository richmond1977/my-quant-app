import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from FinMind.data import DataLoader
import yfinance as yf

# --- 1. 頁面配置 ---
st.set_page_config(page_title="正二量化特助", layout="wide")

# --- 2. 核心計算函式 (FinMind 版) ---
@st.cache_data(ttl=3600)
def fetch_data_finmind(stock_id, years=3.5):
    """使用 FinMind 抓取台股數據並計算五線譜"""
    try:
        dl = DataLoader()
        # 移除可能存在的 .TW 綴詞
        clean_id = stock_id.replace(".TW", "").replace(".tw", "")
        
        start_date = (datetime.now() - timedelta(days=int(years * 365.25))).strftime('%Y-%m-%d')
        
        # 抓取台股日成交資料
        df = dl.taiwan_stock_daily(stock_id=clean_id, start_date=start_date)
        
        if df.empty:
            return None
            
        # 轉換格式以符合後續計算
        df = df.rename(columns={'date': 'Date', 'close': 'Close'})
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        
        # 計算線性回歸
        df['t'] = np.arange(len(df))
        slope, intercept = np.polyfit(df['t'], df['Close'], 1)
        df['Trend'] = slope * df['t'] + intercept
        
        # 標準差與位階
        std_dev = (df['Close'] - df['Trend']).std()
        curr_price = float(df['Close'].iloc[-1])
        curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
        
        return {"df": df, "curr_price": curr_price, "curr_sd": curr_sd, "std_dev": std_dev}
    except Exception as e:
        st.error(f"FinMind 數據抓取異常 ({stock_id}): {e}")
        return None

@st.cache_data(ttl=3600)
def get_vix_indicator():
    """抓取 VIX 指數 (使用 yfinance, 美股指數相對穩定)"""
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        if isinstance(vix_data.columns, pd.MultiIndex):
            vix_data.columns = vix_data.columns.get_level_values(0)
        return float(vix_data['Close'].iloc[-1])
    except:
        return 20.0 # 抓不到時回傳預設常態值

def get_target_weights(sd_level, vix):
    """您的核心權重策略：成長 50% / 波動 20% / 儲備 30%"""
    if sd_level >= 2.0:      
        w = {"Growth": 0.15, "Harvest": 0.10, "Buffer": 0.75}
    elif sd_level <= -2.0:   
        w = {"Growth": 0.80, "Harvest": 0.20, "Buffer": 0.00}
    else:                    
        w = {"Growth": 0.50, "Harvest": 0.20, "Buffer": 0.30}
    
    # VIX 風控
    if vix > 30:
        cut = w["Growth"] * 0.5
        w["Growth"] -= cut
        w["Buffer"] += cut
    return w

# --- 3. 主介面邏輯 ---
st.title("🛡️ 正二槓桿：量化科學投資監控 (FinMind 穩定版)")
st.sidebar.header("🏦 資產配置中心 (TWD)")
total_assets = st.sidebar.number_input("當前可投入總資金", value=1000000, step=100000)

try:
    vix = get_vix_indicator()
    
    with st.spinner('正在同步市場數據...'):
        # 成長桶：00675L + 00670L
        tw_equity = fetch_data_finmind("00675L")
        us_equity = fetch_data_finmind("00670L") # 00670L 亦在台股掛牌
        # 波動桶：00708L
        gold_2x = fetch_data_finmind("00708L")

    if tw_equity and us_equity and gold_2x:
        # 以 00675L 為主要位階參考點
        weights = get_target_weights(tw_equity['curr_sd'], vix)
        
        # 指標顯示
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("00675L 位階", f"{tw_equity['curr_sd']:.2f} SD")
        c2.metric("VIX 恐慌指數", f"{vix:.2f}")
        c3.metric("00670L 現價", f"{us_equity['curr_price']:.2f}")
        c4.metric("00708L 現價", f"{gold_2x['curr_price']:.2f}")

        # 繪製 00675L 五線譜圖表
        st.subheader("📊 00675L 樂活五線譜趨勢")
        df_p = tw_equity['df']
        sd = tw_equity['std_dev']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Close'], name="價格", line=dict(color='black')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend'], name="趨勢線", line=dict(color='gray', dash='dot')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']+2*sd, name="樂觀線(+2SD)", line=dict(color='red')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['Trend']-2*sd, name="悲觀線(-2SD)", line=dict(color='green')))
        st.plotly_chart(fig, use_container_width=True)

        # 再平衡指令
        st.subheader("🛠️ 本日再平衡操作建議")
        growth_total = total_assets * weights['Growth']
        growth_each = growth_total / 2
        
        rebalance_table = [
            {"項目": "成長桶 - 台股正二 (00675L)", "佔比": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{growth_each:,.0f}"},
            {"項目": "成長桶 - 美股正二 (00670L)", "佔比": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{growth_each:,.0f}"},
            {"項目": "波動桶 - 黃金正二 (00708L)", "佔比": f"{weights['Harvest']*100:.1f}%", "目標金額": f"{total_assets * weights['Harvest']:,.0f}"},
            {"項目": "儲備桶 - 現金/短債", "佔比": f"{weights['Buffer']*100:.1f}%", "目標金額": f"{total_assets * weights['Buffer']:,.0f}"}
        ]
        st.table(pd.DataFrame(rebalance_table))

        # 策略警示
        if vix > 30:
            st.warning("🚨 觸及 VIX 防禦機制：成長桶權重已自動減半。")
        
        if tw_equity['curr_sd'] <= -1.5:
            st.success("💰 市場進入悲觀區間，此時增加正二曝險具備極高盈虧比。")
        elif tw_equity['curr_sd'] >= 1.5:
            st.error("⚠️ 市場過熱，請嚴格執行再平衡，鎖定正二獲利。")
        else:
            st.info("⚖️ 目前處於常態波動區間，請依據權重比例維持香儂惡魔配置。")

    else:
        st.error("⚠️ 數據源連線失敗。這可能是因為 FinMind 免費版流量限制，請稍候再重新整理頁面。")

except Exception as e:
    st.error(f"系統發生非預期錯誤: {e}")

st.markdown("---")
st.caption(f"最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 數據源：FinMind & Yahoo Finance")