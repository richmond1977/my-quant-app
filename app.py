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
    if ".TW" not in symbol:
        symbol = f"{symbol}.TW"
            
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(years * 365.25))
    
    df = yf.download(symbol, start=start_date, end=end_date)
    if df.empty:
        return None
    
    df = df[['Adj Close']].dropna()
    df['t'] = np.arange(len(df))
    
    # 線性回歸 (趨勢線)
    slope, intercept = np.polyfit(df['t'], df['Adj Close'], 1)
    df['Trend'] = slope * df['t'] + intercept
    
    # 標準差與位階
    std_dev = (df['Adj Close'] - df['Trend']).std()
    curr_price = float(df['Adj Close'].iloc[-1])
    curr_sd = (curr_price - df['Trend'].iloc[-1]) / std_dev
    
    return {"df": df, "curr_price": curr_price, "curr_sd": curr_sd, "std_dev": std_dev}

@st.cache_data(ttl=3600)
def get_vix_indicator():
    """抓取 VIX 指數作為全球風險斷路器"""
    vix_data = yf.download("^VIX", period="1d")
    return float(vix_data['Adj Close'].iloc[-1])

def get_target_weights(sd_level, vix):
    """根據 00675L 位階與 VIX 決定三桶權重邏輯 (更新版)"""
    # 基礎權重配置：成長 50% / 波動 20% / 儲備 30%
    if sd_level >= 2.0:      # 樂觀線 (+2SD)
        w = {"Growth": 0.15, "Harvest": 0.10, "Buffer": 0.75}
    elif sd_level <= -2.0:   # 悲觀線 (-2SD)
        w = {"Growth": 0.80, "Harvest": 0.20, "Buffer": 0.00}
    else:                    # 趨勢線 (0 SD)
        w = {"Growth": 0.50, "Harvest": 0.20, "Buffer": 0.30}
    
    # VIX 風控：大於 30 成長桶曝險強制減半，移往儲備桶
    if vix > 30:
        cut = w["Growth"] * 0.5
        w["Growth"] -= cut
        w["Buffer"] += cut
    return w

# --- 3. 側邊欄設定 ---
st.sidebar.header("🏦 資產配置中心 (TWD)")
total_assets = st.sidebar.number_input("當前可投入總資金", value=1000000, step=100000)
st.sidebar.markdown("---")
st.sidebar.markdown(f"""
**當前策略配置：**
- **成長桶 (50%)**: 00675L + 00670L
- **波動桶 (20%)**: 00708L
- **儲備桶 (30%)**: 現金/短債
""")

# --- 4. 主介面邏輯 ---
st.title("🛡️ 正二槓桿：量化科學投資監控")
st.caption("策略：整合香儂惡魔、凱利公式與樂活五線譜 (成長桶 50% 配置版)")

try:
    vix = get_vix_indicator()
    
    # 分析三大核心標的
    tw_equity = fetch_data_and_analyze("00675L") # 台灣加權正2
    us_equity = fetch_data_and_analyze("00670L") # Nasdaq正2
    gold_2x = fetch_data_and_analyze("00708L")   # 黃金正2

    if tw_equity and us_equity and gold_2x:
        # 以台股正二 (00675L) 作為主要位階參考點
        weights = get_target_weights(tw_equity['curr_sd'], vix)
        
        # 指標顯示
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("00675L 位階", f"{tw_equity['curr_sd']:.2f} SD")
        c2.metric("VIX 恐慌指數", f"{vix:.2f}")
        c3.metric("00670L 現價", f"{us_equity['curr_price']:.2f}")
        c4.metric("00708L 現價", f"{gold_2x['curr_price']:.2f}")

        # 五線譜圖表
        st.subheader("📊 00675L 樂活五線譜趨勢 (策略基準線)")
        df = tw_equity['df']
        sd = tw_equity['std_dev']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Adj Close'], name="價格", line=dict(color='black')))
        fig.add_trace(go.Scatter(x=df.index, y=df['Trend'], name="趨勢線", line=dict(color='gray', dash='dot')))
        fig.add_trace(go.Scatter(x=df.index, y=df['Trend']+2*sd, name="樂觀線(+2SD)", line=dict(color='red', width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=df['Trend']-2*sd, name="悲觀線(-2SD)", line=dict(color='green', width=1)))
        st.plotly_chart(fig, use_container_width=True)

        # 執行指令
        st.subheader("🛠️ 本日再平衡操作建議")
        
        # 成長桶內部平分 (25% + 25%)
        growth_total = total_assets * weights['Growth']
        growth_each = growth_total / 2
        
        rebalance_table = [
            {"桶類別": "成長桶 - 台股 (00675L)", "比例": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{growth_each:,.0f}"},
            {"桶類別": "成長桶 - 美股 (00670L)", "比例": f"{weights['Growth']/2*100:.1f}%", "目標金額": f"{growth_each:,.0f}"},
            {"桶類別": "波動桶 - 黃金 (00708L)", "比例": f"{weights['Harvest']*100:.1f}%", "目標金額": f"{total_assets * weights['Harvest']:,.0f}"},
            {"桶類別": "儲備桶 - 現金/短債", "比例": f"{weights['Buffer']*100:.1f}%", "目標金額": f"{total_assets * weights['Buffer']:,.0f}"}
        ]
        st.table(pd.DataFrame(rebalance_table))

        # 策略提醒
        if vix > 30:
            st.warning(f"🚨 VIX > 30 觸發防禦：成長桶已由 50% 調降至 {weights['Growth']*100:.0f}%。")
        
        if tw_equity['curr_sd'] <= -2.0:
            st.success("💰 觸及悲觀線！建議執行全額曝險，捕捉均值回歸初期的爆發力。")
        elif tw_equity['curr_sd'] >= 2.0:
            st.error("⚠️ 觸及樂觀線！成長桶應縮減至 15% 基礎水位，鎖定獲利。")
        else:
            st.info("⚖️ 正常位階。成長桶維持 50% 配置，利用 00675L 與 00670L 進行跨國收割。")

except Exception as e:
    st.error(f"數據連線異常。錯誤代碼: {e}")

st.markdown("---")
st.caption(f"最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 您的專屬 AI 特助")
