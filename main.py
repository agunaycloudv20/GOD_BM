import streamlit as st
import google.generativeai as genai
import json
from PIL import Image
import feedparser
from datetime import datetime
import pytz
import ccxt
import pandas as pd
import sqlite3
import io
import streamlit.components.v1 as components
import streamlit as st

# Şifreleri "Gizli Kasa"dan (Secrets) çekiyoruz
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    OKX_API_KEY = st.secrets["OKX_API_KEY"]
    OKX_SECRET = st.secrets["OKX_SECRET"]
    OKX_PASSWORD = st.secrets["OKX_PASSWORD"]
except:
    # Eğer bilgisayarında test ediyorsan ve hata alırsan buraya manuel yazabilirsin ama tavsiye edilmez
    GOOGLE_API_KEY = ""
    OKX_API_KEY = ""
    OKX_SECRET = ""
    OKX_PASSWORD = ""
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except: pass

def init_db():
    conn = sqlite3.connect('god_gm_v20.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY, date TEXT, symbol TEXT, strategy TEXT, action TEXT, score INTEGER, log TEXT, img BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades 
                 (id INTEGER PRIMARY KEY, date TEXT, symbol TEXT, side TEXT, size REAL, pnl REAL, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. KURUMSAL TASARIM (HAAUB UI)
# ==========================================
st.set_page_config(page_title="HAAUB | STRATEGY CORE", layout="wide", page_icon="🦅", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700&family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* HEADER */
    .haaub-header {
        text-align: center; padding: 20px 0; background: #020202; border-bottom: 1px solid #222;
        margin-top: -60px; margin-bottom: 0;
    }
    .brand-title { font-family: 'Cinzel', serif; font-size: 26px; letter-spacing: 6px; color: #fff; }
    .brand-subtitle { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #f0b90b; letter-spacing: 3px; margin-top: 5px; }
    
    /* STATUS BAR */
    .status-bar {
        background: #0a0a0a; border-bottom: 1px solid #222; padding: 6px 20px;
        font-family: 'JetBrains Mono', monospace; font-size: 11px; display: flex; justify-content: space-between;
    }
    
    /* TICKER (Çakışma Düzeltildi) */
    .ticker-wrap {
        width: 100%; background: #0E1113; border-bottom: 1px solid #333;
        white-space: nowrap; padding: 8px 0; overflow: hidden; margin-bottom: 20px;
    }
    .ticker { display: inline-block; animation: marquee 60s linear infinite; }
    .ticker:hover { animation-play-state: paused; cursor: default; }
    @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
    .ticker-item { padding: 0 40px; color: #888; font-size: 11px; font-family: 'JetBrains Mono'; }
    
    /* BUTONLAR */
    .stButton>button {
        border-radius: 0px; background: #111; border: 1px solid #333; color: #888;
        font-weight: 600; font-family: 'Inter'; font-size: 10px; width: 100%; height: 35px;
        transition: all 0.2s;
    }
    .stButton>button:hover { border-color: #f0b90b; color: #f0b90b; background: #1a1a1a; }
    
    /* STRATEGY CARD */
    .strategy-card {
        border-left: 3px solid #f0b90b; background: #0E1113; padding: 15px; margin-top: 10px;
    }
    .strat-name { color: #f0b90b; font-family: 'Cinzel'; font-size: 14px; letter-spacing: 1px; }
    
    /* DOCK */
    .dock-container { margin-top: 30px; border-top: 2px solid #f0b90b; background: #0E1113; padding: 20px; min-height: 150px; }
    
    header {visibility: hidden;} footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. INTELLIGENCE MOTORU
# ==========================================

def get_session_status():
    utc = datetime.now(pytz.utc).hour
    sessions = {"SYDNEY": (21, 6), "TOKYO": (23, 8), "LONDON": (8, 17), "NEW YORK": (13, 22)}
    active = []
    for name, (s, e) in sessions.items():
        is_open = (s <= utc < e) if s < e else (s <= utc or utc < e)
        if is_open: active.append(name)
    if "LONDON" in active and "NEW YORK" in active: return "🟢 LONDON & NY OVERLAP"
    if active: return f"🟢 {' & '.join(active)} OPEN"
    return "🔴 MARKETS CLOSED"

def get_wallet():
    try:
        ex = ccxt.okx({'apiKey': OKX_API_KEY, 'secret': OKX_SECRET, 'password': OKX_PASSWORD})
        return ex.fetch_balance()['USDT']['free']
    except: return 0.00

def get_open_positions_df():
    try:
        ex = ccxt.okx({'apiKey': OKX_API_KEY, 'secret': OKX_SECRET, 'password': OKX_PASSWORD})
        pos = ex.fetch_positions()
        if pos:
            d = [[p['symbol'], p['side'].upper(), p['contracts'], p['entryPrice'], p['unrealizedPnl']] for p in pos]
            return pd.DataFrame(d, columns=['SYMBOL', 'SIDE', 'SIZE', 'ENTRY', 'PNL'])
    except: pass
    return pd.DataFrame(columns=['SYMBOL', 'SIDE', 'SIZE', 'ENTRY', 'PNL'])

def analyze_with_strategy_selector(image, symbol):
    """
    MASTER INTELLIGENCE: 
    Grafiğe bakar, stratejileri yarıştırır, en iyisini seçer ve analizi ona göre yapar.
    """
    prompt = f"""
    **ROLE:** HAAUB Global Strategy Architect (AI).
    **ASSET:** {symbol}
    
    **PROTOCOL:**
    1. **SCAN:** Analyze Market Structure (Trending, Ranging, Volatile, Manipulation).
    2. **TOURNAMENT:** Evaluate this chart against these 5 strategies:
       - A) Trend Following (EMA/MA Cross)
       - B) Smart Money Concepts (SMC - Liquidity Sweep/Order Block)
       - C) Mean Reversion (RSI/Bollinger - Overbought/Oversold)
       - D) Momentum / Breakout (Volume Spike)
       - E) Orderflow / CVD
    3. **SELECTION:** Choose the SINGLE BEST strategy with the highest win probability for THIS specific chart.
    4. **EXECUTION:** Generate trade setup using ONLY the rules of the selected strategy.
    
    **OUTPUT FORMAT (JSON ONLY):**
    {{
        "selected_strategy": "Name of Winning Strategy (e.g. SMC)",
        "match_score": 95, (0-100 suitability score)
        "reasoning": "Why this strategy won? (e.g. 'Market is ranging, Trend Following invalid. SMC detected liquidity sweep.')",
        "action": "LONG / SHORT / WAIT",
        "log": "Technical Analysis details (Turkish).",
        "setup": {{ "entry": 0.0, "sl": 0.0, "tp": 0.0 }}
    }}
    """
    try:
        res = model.generate_content([prompt, image])
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except: return None

def get_news():
    try: return feedparser.parse('https://cointelegraph.com/rss').entries[:10]
    except: return []

# ==========================================
# 4. ARAYÜZ
# ==========================================

# HEADER
st.markdown("""
<div class="haaub-header">
    <div class="brand-title">HAAUB & CO</div>
    <div class="brand-subtitle">GOD BM: STRATEGY CORE</div>
</div>
""", unsafe_allow_html=True)

# STATUS BAR
tr_time = datetime.now(pytz.timezone('Europe/Istanbul')).strftime("%H:%M")
session = get_session_status()
st.markdown(f"""
<div class="status-bar">
    <span>SYSTEM STATUS: <span style="color:#00ff00;">OPERATIONAL</span></span>
    <span>TSI {tr_time} <span style="color:#666; margin:0 5px;">|</span> {session}</span>
</div>
""", unsafe_allow_html=True)

# TICKER
news = get_news()
news_txt = "   +++   ".join([f"⚡ {n.title}" for n in news])
st.markdown(f'<div class="ticker-wrap"><div class="ticker"><span class="ticker-item">{news_txt}</span></div></div>', unsafe_allow_html=True)

# STATE
if 'selected_tf' not in st.session_state: st.session_state.selected_tf = '4h'

col_left, col_mid, col_right = st.columns([1, 3.5, 1.5])

# === SOL PANEL ===
with col_left:
    st.markdown("### CONTROL")
    st.markdown(f"""
    <div style="background:#0E1113; border:1px solid #333; padding:15px; margin-bottom:20px;">
        <div style="font-size:10px; color:#666;">EQUITY (USDT)</div>
        <div style="font-size:24px; color:#fff; font-family:'JetBrains Mono';">${get_wallet():,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
    
    symbol = st.selectbox("ASSET", ["BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT"], label_visibility="collapsed")
    
    st.markdown("---")
    st.caption("TIMEFRAME")
    
    # GRID BUTTONS
    c1, c2, c3 = st.columns(3)
    if c1.button("15M"): st.session_state.selected_tf = '15m'
    if c2.button("30M"): st.session_state.selected_tf = '30m'
    if c3.button("1H"): st.session_state.selected_tf = '1h'
    c4, c5, c6 = st.columns(3)
    if c4.button("2H"): st.session_state.selected_tf = '2h'
    if c5.button("4H"): st.session_state.selected_tf = '4h'
    if c6.button("1D"): st.session_state.selected_tf = '1d'
    st.markdown(f"<div style='text-align:center; font-size:10px; color:#f0b90b; margin-top:5px;'>ACTIVE: {st.session_state.selected_tf.upper()}</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    if st.button("RESET SYSTEM"): st.session_state.clear(); st.rerun()

# === ORTA PANEL ===
with col_mid:
    tabs = st.tabs(["🔴 LIVE MONITOR", "🧠 ARCHITECT SCAN", "🗄️ DATABASE"])
    
    # LIVE
    with tabs[0]:
        tv_sym = f"OKX:{symbol.replace('/','')}"
        tv_tf = st.session_state.selected_tf.replace('1h','60').replace('2h','120').replace('4h','240').replace('1d','D').replace('15m','15').replace('30m','30')
        components.html(f"""
        <div class="tradingview-widget-container">
          <div id="tv"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{"width": "100%", "height": 500, "symbol": "{tv_sym}", "interval": "{tv_tf}", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "container_id": "tv"}});
          </script>
        </div>""", height=510)

    # ARCHITECT SCAN
    with tabs[1]:
        st.info("Upload Chart. The Architect will select the best strategy.")
        uploaded = st.file_uploader("Img", type=['png','jpg'], label_visibility="collapsed")
        
        if uploaded and st.button("RUN STRATEGY TOURNAMENT", type="primary"):
            with st.spinner("EVALUATING STRATEGIES... SELECTING BEST FIT... CALCULATING ENTRIES..."):
                img = Image.open(uploaded)
                res = analyze_with_strategy_selector(img, symbol)
                if res:
                    st.session_state.ai_res = res
                    # DB Save
                    buf = io.BytesIO(); img.save(buf, format='PNG')
                    conn = sqlite3.connect('god_gm_v20.db'); c = conn.cursor()
                    c.execute("INSERT INTO history (date, symbol, strategy, action, score, log, img) VALUES (?,?,?,?,?,?,?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), symbol, res['selected_strategy'], res['action'], res['match_score'], res['log'], buf.getvalue()))
                    conn.commit(); conn.close()

        if 'ai_res' in st.session_state:
            r = st.session_state.ai_res
            clr = "#0ecb81" if r['action']=="LONG" else "#f6465d" if r['action']=="SHORT" else "#888"
            
            # STRATEGY CARD
            st.markdown(f"""
            <div class="strategy-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="color:#666; font-size:10px;">WINNING STRATEGY</div>
                        <div class="strat-name">{r['selected_strategy'].upper()}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#666; font-size:10px;">FIT SCORE</div>
                        <div style="color:#fff; font-size:18px; font-family:'JetBrains Mono';">{r['match_score']}%</div>
                    </div>
                </div>
                <hr style="border-color:#333; margin:10px 0;">
                <div style="font-size:12px; color:#ccc; font-style:italic;">"{r['reasoning']}"</div>
            </div>
            
            <div style="margin-top:10px; padding:15px; background:#0E1113; border-left:4px solid {clr};">
                <h2 style="margin:0; color:{clr};">{r['action']}</h2>
                <p style="color:#ccc; font-size:13px; margin-top:5px;">{r['log']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("⚡ AUTO-FILL EXECUTION PANEL"):
                st.session_state.fill_setup = r['setup']
                st.toast("Order details copied!", icon="📋")

    # DB
    with tabs[2]:
        conn = sqlite3.connect('god_gm_v20.db')
        df = pd.read_sql_query("SELECT id, date, symbol, strategy, action, score FROM history ORDER BY id DESC LIMIT 20", conn)
        st.dataframe(df, use_container_width=True, hide_index=True)

# === SAĞ PANEL ===
with col_right:
    st.markdown("### EXECUTION")
    setup = st.session_state.get('fill_setup', {})
    
    with st.form("exec"):
        st.caption("SMART ORDER")
        price = st.number_input("ENTRY", value=float(setup.get('entry', 0.0)))
        stop = st.number_input("STOP LOSS", value=float(setup.get('sl', 0.0)))
        target = st.number_input("TARGET", value=float(setup.get('tp', 0.0)))
        
        st.markdown("---")
        size = st.number_input("SIZE ($)", value=100.0)
        lev = st.slider("LEV", 1, 100, 10)
        
        c1, c2 = st.columns(2)
        if c1.form_submit_button("BUY / LONG"): st.toast("LONG Placed")
        if c2.form_submit_button("SELL / SHORT"): st.toast("SHORT Placed")

    st.markdown("---")
    st.markdown("### CALENDAR")
    st.caption("No High-Impact Events")

# === DOCKING STATION ===
st.markdown("""
<div class="dock-container">
    <div class="dock-header">⚡ DOCKING STATION: ACTIVE POSITIONS</div>
</div>
""", unsafe_allow_html=True)

df_pos = get_open_positions_df()
if not df_pos.empty: st.dataframe(df_pos, use_container_width=True)
else: st.markdown("<div style='color:#444; text-align:center; border:1px dashed #333; padding:10px;'>NO ACTIVE POSITIONS</div>", unsafe_allow_html=True)

# FOOTER
st.markdown("""
<div style="text-align:center; padding:30px; color:#333; font-size:10px; letter-spacing:2px; margin-top:20px; font-family:'JetBrains Mono';">
    HAAUB & CO | GLOBAL BUSINESS MACHINES | v20.0 CORE
</div>
""", unsafe_allow_html=True)