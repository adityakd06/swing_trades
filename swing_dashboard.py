"""
swing_dashboard.py — NSE Swing Trader (fixed version)
Run: py -3.12 -m streamlit run swing_dashboard.py
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import time
from datetime import datetime

from indicators import calc_swing_setup, calc_support_resistance, calc_holding_period
from scanner import scan_stocks, NSE_UNIVERSE
from journal import load_journal, add_trade, close_trade, get_summary, update_open_prices

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="NSE Swing Trader", page_icon="🎯", layout="wide",
                   initial_sidebar_state="expanded")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@700;800&display=swap');
html, body, [class*="css"] { font-family:'JetBrains Mono',monospace!important; background:#060d06!important; color:#b8f5b8!important; }
.stApp { background:#060d06!important; }
section[data-testid="stSidebar"] { background:#0a130a!important; border-right:1px solid #1a2e1a!important; }
section[data-testid="stSidebar"] * { color:#b8f5b8!important; }
h2,h3 { color:#00ff88!important; font-family:'Syne',sans-serif!important; }
hr { border-color:#1a2e1a!important; }
.stTabs [data-baseweb="tab-list"] { background:#0a130a!important; border-bottom:1px solid #1a2e1a!important; }
.stTabs [data-baseweb="tab"] { color:#2d6b2d!important; font-family:'JetBrains Mono'!important; }
.stTabs [aria-selected="true"] { color:#00ff88!important; border-bottom:2px solid #00ff88!important; }
.stButton>button { background:rgba(0,255,136,0.08)!important; border:1px solid #00ff88!important; color:#00ff88!important; font-family:'JetBrains Mono',monospace!important; font-weight:600!important; border-radius:8px!important; }
.stButton>button:hover { background:rgba(0,255,136,0.18)!important; }
.footer { font-size:9px; color:#2d6b2d; text-align:center; padding:16px; border-top:1px solid #1a2e1a; margin-top:20px; }
</style>
""", unsafe_allow_html=True)


# ── Safe HTML helpers (no nested Python in f-strings) ─────────────────────────
def card(html):
    st.markdown(
        '<div style="background:#0a130a;border:1px solid #1a2e1a;border-radius:12px;padding:14px 16px;margin-bottom:10px">'
        + html + '</div>',
        unsafe_allow_html=True
    )

def lbl(text):
    return f'<div style="font-size:9px;color:#2d6b2d;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">{text}</div>'

def val_big(text, color, size=20):
    return f'<div style="font-family:Syne,sans-serif;font-size:{size}px;font-weight:800;color:{color}">{text}</div>'

def stat_box(label_text, value_text, color):
    return (
        '<div style="flex:1;background:#060d06;border:1px solid #1a2e1a;border-radius:8px;padding:8px;text-align:center">'
        + f'<div style="font-size:8px;color:#2d6b2d;letter-spacing:1px">{label_text}</div>'
        + f'<div style="font-size:14px;font-weight:700;color:{color}">{value_text}</div>'
        + '</div>'
    )

def level_box(bg, border, label_text, value_text, color):
    return (
        f'<div style="background:{bg};border:1px solid {border};border-radius:8px;padding:10px;margin-bottom:6px">'
        + lbl(label_text)
        + f'<div style="font-size:20px;font-weight:700;color:{color}">{value_text}</div>'
        + '</div>'
    )


# ── Header ────────────────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
st.markdown(
    '<div style="border-bottom:1px solid #1a2e1a;padding-bottom:14px;margin-bottom:20px">'
    '<div style="font-size:9px;color:#00ff88;letter-spacing:4px;text-transform:uppercase;margin-bottom:4px">NSE · SWING TRADER · LIVE</div>'
    '<div style="font-family:Syne,sans-serif;font-size:28px;font-weight:800;color:#00ff88">🎯 Swing Trade Dashboard</div>'
    f'<div style="font-size:10px;color:#2d6b2d;margin-top:4px">MACD · RSI · Bollinger Bands · ATR Stop-Loss · Trade Journal &nbsp;|&nbsp; {now_str}</div>'
    '</div>',
    unsafe_allow_html=True
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## ⚙️ Settings")
st.sidebar.markdown("---")
scan_count = st.sidebar.slider("Max stocks to scan", 20, len(NSE_UNIVERSE), 40, 5)
min_score  = st.sidebar.slider("Min setup score", 0, 100, 30, 5)
min_rr     = st.sidebar.slider("Min R:R Ratio", 1.0, 5.0, 1.5, 0.5)
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Analyse Any Stock")
custom_sym = st.sidebar.text_input("Enter NSE symbol", placeholder="e.g. RELIANCE").upper().strip()
st.sidebar.markdown("---")
if st.sidebar.button("↻ Refresh Scanner"):
    st.cache_data.clear()
    st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Scanner", "📊 Stock Analysis", "📓 Trade Journal", "💰 P&L Tracker"])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCANNER
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### 🔍 Swing Setup Scanner")
    st.caption("Ranks NSE stocks by setup quality using MACD + RSI + Bollinger + EMA scoring")

    @st.cache_data(ttl=900, show_spinner=False)
    def run_scan(n):
        return scan_stocks(max_stocks=n)

    with st.spinner("⏳ Scanning NSE stocks... (~2 min first time)"):
        scan_df = run_scan(scan_count)

    if scan_df.empty:
        st.error("No setups found. Try increasing scan count or lowering min score.")
    else:
        filtered_scan = scan_df[
            (scan_df["Score"] >= min_score) &
            (scan_df["R:R Ratio"] >= min_rr)
        ]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stocks Scanned", len(scan_df))
        c2.metric("Valid Setups",   len(filtered_scan))
        c3.metric("A+ Setups 🔥",  len(filtered_scan[filtered_scan["Quality"].str.startswith("A+")]))
        c4.metric("B Setups ✅",   len(filtered_scan[filtered_scan["Quality"].str.startswith("B")]))
        st.markdown("<br>", unsafe_allow_html=True)

        display_cols = ["Symbol","Price ₹","Change %","Score","Quality","Entry ₹",
                        "Stop Loss ₹","Target 2 ₹","R:R Ratio","RSI","EMA20","EMA50","Vol Ratio"]

        def style_scan(df):
            s = pd.DataFrame("", index=df.index, columns=df.columns)
            for i, row in df.iterrows():
                if "Change %" in df.columns:
                    s.at[i,"Change %"] = "color:#00ff88" if row["Change %"] >= 0 else "color:#ff4d6d"
                if "Score" in df.columns:
                    sc = row["Score"]
                    c  = "#00ff88" if sc >= 70 else "#38bdf8" if sc >= 50 else "#f59e0b"
                    s.at[i,"Score"] = f"color:{c};font-weight:700"
                if "R:R Ratio" in df.columns:
                    s.at[i,"R:R Ratio"] = "color:#00ff88;font-weight:700" if row["R:R Ratio"] >= 2 else ""
                if "RSI" in df.columns:
                    s.at[i,"RSI"] = "color:#00ff88" if row["RSI"] < 40 else "color:#ff4d6d" if row["RSI"] > 70 else ""
            return s

        if not filtered_scan.empty:
            st.dataframe(
                filtered_scan[display_cols].style.apply(style_scan, axis=None).format({
                    "Price ₹":"₹{:.2f}","Change %":"{:+.2f}%","Entry ₹":"₹{:.2f}",
                    "Stop Loss ₹":"₹{:.2f}","Target 2 ₹":"₹{:.2f}","R:R Ratio":"{:.1f}x",
                    "RSI":"{:.1f}","EMA20":"₹{:.2f}","EMA50":"₹{:.2f}",
                    "Vol Ratio":"{:.1f}x","Score":"{:.0f}",
                }),
                use_container_width=True, height=420
            )

        st.markdown("---")
        st.markdown("#### ➕ Log Trade from Scanner")
        top_syms = filtered_scan["Symbol"].tolist()
        if top_syms:
            ca, cb, cc, cd = st.columns([2,1,1,1])
            with ca: j_sym   = st.selectbox("Symbol", top_syms, key="scanner_sym")
            with cb: j_qty   = st.number_input("Qty", min_value=1, value=10, key="scanner_qty")
            with cc: j_notes = st.text_input("Notes", key="scanner_notes")
            with cd:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📓 Log Trade", key="scanner_log"):
                    row = filtered_scan[filtered_scan["Symbol"] == j_sym].iloc[0]
                    tid = add_trade(j_sym, row["Entry ₹"], row["Stop Loss ₹"],
                                    row["Target 1 ₹"], row["Target 2 ₹"], j_qty, j_notes)
                    st.success(f"✅ Trade #{tid} logged for {j_sym}!")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — STOCK ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📊 Deep Stock Analysis")

    sym_options = ([custom_sym] if custom_sym else [])
    if not scan_df.empty:
        sym_options += scan_df["Symbol"].tolist()
    sym_options = sym_options or NSE_UNIVERSE[:20]

    cs1, cs2 = st.columns([2,1])
    with cs1: analysis_sym    = st.selectbox("Select or type symbol", sym_options, key="analysis_sym")
    with cs2: analysis_period = st.selectbox("History", ["3mo","6mo","1y"], index=1)

    @st.cache_data(ttl=600, show_spinner=False)
    def fetch_and_analyse(sym, period):
        try:
            time.sleep(0.5)
            ticker = yf.Ticker(sym + ".NS")
            data   = ticker.history(period=period, interval="1d")
            if data.empty or len(data) < 60:
                return None, None, None
            setup   = calc_swing_setup(data)
            sup_res = calc_support_resistance(data)
            return data, setup, sup_res
        except Exception:
            return None, None, None

    with st.spinner(f"Analysing {analysis_sym}..."):
        data, setup, sr = fetch_and_analyse(analysis_sym, analysis_period)

    if data is None:
        st.error("Could not fetch data. Check symbol name.")
    else:
        support, resistance = sr
        col_l, col_r = st.columns([1, 2])

        with col_l:
            # ── Stock header ──────────────────────────────────────────────────
            card(
                val_big(analysis_sym, "#00ff88", 20)
                + '<div style="font-size:10px;color:#2d6b2d">NSE · Equity</div>'
                + f'<div style="font-family:Syne,sans-serif;font-size:26px;font-weight:800;color:#fff;margin-top:6px">&#8377;{setup["price"]}</div>'
            )

            # ── Quality bar ───────────────────────────────────────────────────
            sc = setup["quality_color"]
            sp = setup["score"]
            card(
                lbl("SETUP QUALITY")
                + f'<div style="font-size:20px;font-weight:700;color:{sc};margin-bottom:8px">{setup["quality"]}</div>'
                + '<div style="height:8px;background:#1a2e1a;border-radius:4px;margin-bottom:4px">'
                + f'<div style="height:100%;width:{sp}%;background:{sc};border-radius:4px"></div></div>'
                + f'<div style="font-size:10px;color:#2d6b2d">Score: {sp} / 100</div>'
            )

            # ── Levels ────────────────────────────────────────────────────────
            card(
                level_box("rgba(56,189,248,0.08)", "rgba(56,189,248,0.25)",
                          "ENTRY", f'&#8377;{setup["entry"]}', "#38bdf8")
                + level_box("rgba(255,77,109,0.08)", "rgba(255,77,109,0.25)",
                            f'STOP LOSS (1.5x ATR) — Risk &#8377;{setup["risk"]}',
                            f'&#8377;{setup["stop_loss"]}', "#ff4d6d")
                + level_box("rgba(0,255,136,0.06)", "rgba(0,255,136,0.2)",
                            "TARGET 1 (2x ATR)", f'&#8377;{setup["target_1"]}', "#00ff88")
                + level_box("rgba(0,255,136,0.12)", "rgba(0,255,136,0.4)",
                            f'TARGET 2 (3x ATR) — Reward &#8377;{setup["reward"]}',
                            f'&#8377;{setup["target_2"]}', "#00ff88")
            )

            # ── Key stats row ─────────────────────────────────────────────────
            rr_color  = "#00ff88" if setup["rr_ratio"] >= 2 else "#f59e0b"
            rsi_color = "#00ff88" if setup["rsi"] < 40 else "#ff4d6d" if setup["rsi"] > 70 else "#b8f5b8"
            row_html  = (
                '<div style="display:flex;gap:6px;margin-bottom:10px">'
                + stat_box("R:R",   f'{setup["rr_ratio"]}x',   rr_color)
                + stat_box("ATR",   f'&#8377;{setup["atr"]}',  "#b8f5b8")
                + stat_box("RSI",   str(setup["rsi"]),          rsi_color)
                + stat_box("EMA20", f'&#8377;{setup["ema20"]}', "#b8f5b8")
                + stat_box("EMA50", f'&#8377;{setup["ema50"]}', "#b8f5b8")
                + '</div>'
            )
            st.markdown(row_html, unsafe_allow_html=True)

            # ── Why this setup ────────────────────────────────────────────────
            if setup["reasons"]:
                reasons_html = "".join(
                    f'<div style="font-size:11px;color:#4a7a4a;padding:3px 0;border-bottom:1px solid #1a2e1a">✓ {r}</div>'
                    for r in setup["reasons"]
                )
                card(lbl("WHY THIS SETUP") + reasons_html)

            # ── Holding period ────────────────────────────────────────────────
            hp = calc_holding_period(data, setup)
            hc = hp["cat_color"]
            hold_html = (
                lbl("HOW LONG TO HOLD?")
                + val_big(hp["category"], hc, 20)
                + f'<div style="font-size:13px;color:#b8f5b8;margin:4px 0 12px">Ideal: <b>{hp["label"]}</b></div>'
                + '<div style="display:flex;gap:6px">'
                + stat_box("MIN",      f'{hp["min_days"]}d',   "#b8f5b8")
                + f'<div style="flex:1;background:#060d06;border:2px solid {hc};border-radius:8px;padding:8px;text-align:center">'
                + f'<div style="font-size:8px;color:#2d6b2d;letter-spacing:1px">IDEAL</div>'
                + f'<div style="font-size:14px;font-weight:700;color:{hc}">{hp["ideal_days"]}d</div></div>'
                + stat_box("MAX STOP", f'{hp["max_days"]}d',   "#b8f5b8")
                + '</div>'
            )
            card(hold_html)

            with st.expander("📋 Why this duration + Exit Rules"):
                st.markdown("**Why this duration:**")
                for r in hp["reasoning"]:
                    st.markdown(f"→ {r}")
                st.markdown("**Exit Rules:**")
                for r in hp["exit_rules"]:
                    st.markdown(r)

            # ── Log trade ─────────────────────────────────────────────────────
            st.markdown("#### ➕ Log This Trade")
            qty_input  = st.number_input("Quantity", min_value=1, value=10, key="analysis_qty")
            note_input = st.text_input("Notes", placeholder="e.g. MACD crossover", key="analysis_note")
            if st.button("📓 Log Trade", key="analysis_log"):
                tid = add_trade(analysis_sym, setup["entry"], setup["stop_loss"],
                                setup["target_1"], setup["target_2"], qty_input, note_input)
                st.success(f"✅ Trade #{tid} logged!")

        # ── Chart ─────────────────────────────────────────────────────────────
        with col_r:
            fig = make_subplots(
                rows=4, cols=1, shared_xaxes=True,
                row_heights=[0.45, 0.20, 0.20, 0.15],
                vertical_spacing=0.025,
                subplot_titles=[
                    f"{analysis_sym} — Candles + EMA + Bollinger",
                    "MACD (12,26,9)", "RSI (14)", "Volume"
                ]
            )

            fig.add_trace(go.Candlestick(
                x=data.index, open=data["Open"], high=data["High"],
                low=data["Low"], close=data["Close"], name="Price",
                increasing_line_color="#00ff88", decreasing_line_color="#ff4d6d",
                increasing_fillcolor="rgba(0,255,136,0.6)",
                decreasing_fillcolor="rgba(255,77,109,0.6)",
            ), row=1, col=1)

            fig.add_trace(go.Scatter(x=data.index, y=setup["bb_upper_series"], name="BB Upper",
                line=dict(color="rgba(56,189,248,0.5)", width=1, dash="dot")), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=setup["bb_lower_series"], name="BB Lower",
                line=dict(color="rgba(56,189,248,0.5)", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(56,189,248,0.03)", showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=setup["bb_mid_series"], name="BB Mid",
                line=dict(color="rgba(56,189,248,0.3)", width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=setup["ema20_series"], name="EMA20",
                line=dict(color="#f59e0b", width=1.5, dash="dash")), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=setup["ema50_series"], name="EMA50",
                line=dict(color="#a78bfa", width=1.5)), row=1, col=1)

            for y_val, clr, txt in [
                (setup["entry"],     "#38bdf8", f'Entry {setup["entry"]}'),
                (setup["stop_loss"], "#ff4d6d", f'Stop {setup["stop_loss"]}'),
                (setup["target_1"],  "rgba(0,255,136,0.6)", f'T1 {setup["target_1"]}'),
                (setup["target_2"],  "#00ff88", f'T2 {setup["target_2"]}'),
            ]:
                fig.add_hline(y=y_val, line_color=clr, line_dash="dash", line_width=1,
                              annotation_text=txt, annotation_font_color=clr,
                              annotation_font_size=9, row=1, col=1)

            for s in support[:2]:
                fig.add_hline(y=s, line_color="rgba(0,255,136,0.2)", line_width=0.8,
                              annotation_text=f"S {round(s,1)}", annotation_font_color="#2d6b2d",
                              annotation_font_size=8, row=1, col=1)
            for r in resistance[:2]:
                fig.add_hline(y=r, line_color="rgba(255,77,109,0.2)", line_width=0.8,
                              annotation_text=f"R {round(r,1)}", annotation_font_color="#ff4d6d",
                              annotation_font_size=8, row=1, col=1)

            hist_colors = [
                "rgba(0,255,136,0.6)" if v >= 0 else "rgba(255,77,109,0.6)"
                for v in setup["macd_hist_series"]
            ]
            fig.add_trace(go.Bar(x=data.index, y=setup["macd_hist_series"],
                name="MACD Hist", marker_color=hist_colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=setup["macd_series"], name="MACD",
                line=dict(color="#00ff88", width=1.5)), row=2, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=setup["macd_sig_series"], name="Signal",
                line=dict(color="#f59e0b", width=1.2, dash="dash")), row=2, col=1)
            fig.add_hline(y=0, line_color="#1a2e1a", line_width=1, row=2, col=1)

            fig.add_trace(go.Scatter(x=data.index, y=setup["rsi_series"], name="RSI",
                line=dict(color="#a78bfa", width=1.5),
                fill="tozeroy", fillcolor="rgba(167,139,250,0.04)"), row=3, col=1)
            fig.add_hline(y=70, line_color="rgba(255,77,109,0.5)", line_dash="dash",
                          line_width=1, annotation_text="70",
                          annotation_font_color="#ff4d6d", annotation_font_size=9, row=3, col=1)
            fig.add_hline(y=30, line_color="rgba(0,255,136,0.5)", line_dash="dash",
                          line_width=1, annotation_text="30",
                          annotation_font_color="#00ff88", annotation_font_size=9, row=3, col=1)
            fig.add_hrect(y0=40, y1=65, fillcolor="rgba(0,255,136,0.03)",
                          line_width=0, row=3, col=1)

            vol_colors = [
                "rgba(0,255,136,0.5)" if c >= o else "rgba(255,77,109,0.5)"
                for c, o in zip(data["Close"], data["Open"])
            ]
            fig.add_trace(go.Bar(x=data.index, y=data["Volume"],
                name="Volume", marker_color=vol_colors), row=4, col=1)

            fig.update_layout(
                height=720, paper_bgcolor="#060d06", plot_bgcolor="#0a130a",
                font=dict(family="JetBrains Mono", color="#b8f5b8", size=10),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", yanchor="bottom", y=1.01,
                            bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
                margin=dict(l=10, r=80, t=40, b=10), hovermode="x unified",
            )
            for i in range(1, 5):
                fig.update_xaxes(gridcolor="#1a2e1a", zeroline=False,
                                 showspikes=True, spikecolor="#00ff88",
                                 spikethickness=1, row=i, col=1)
                fig.update_yaxes(gridcolor="#1a2e1a", zeroline=False, row=i, col=1)

            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRADE JOURNAL
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 📓 Trade Journal")
    j_col1, j_col2 = st.columns([1, 2])

    with j_col1:
        st.markdown("#### ➕ Log New Trade")
        with st.form("new_trade_form"):
            nt_sym   = st.text_input("Symbol", placeholder="RELIANCE").upper()
            nt_entry = st.number_input("Entry Price ₹", min_value=1.0, value=100.0, step=0.5)
            nt_sl    = st.number_input("Stop Loss ₹",   min_value=1.0, value=95.0,  step=0.5)
            nt_t1    = st.number_input("Target 1 ₹",    min_value=1.0, value=108.0, step=0.5)
            nt_t2    = st.number_input("Target 2 ₹",    min_value=1.0, value=112.0, step=0.5)
            nt_qty   = st.number_input("Quantity",       min_value=1,   value=10)
            nt_notes = st.text_input("Notes")
            if st.form_submit_button("📓 Log Trade") and nt_sym:
                tid = add_trade(nt_sym, nt_entry, nt_sl, nt_t1, nt_t2, nt_qty, nt_notes)
                st.success(f"✅ Trade #{tid} logged!")

        st.markdown("---")
        st.markdown("#### ✅ Close a Trade")
        journal     = load_journal()
        open_trades = journal[journal["status"] == "OPEN"] if not journal.empty else pd.DataFrame()
        if not open_trades.empty:
            with st.form("close_trade_form"):
                close_id   = st.selectbox(
                    "Trade ID", open_trades["id"].tolist(),
                    format_func=lambda x: f"#{x} — {open_trades[open_trades['id']==x]['symbol'].values[0]}"
                )
                exit_price = st.number_input("Exit Price ₹", min_value=1.0, value=100.0, step=0.5)
                close_note = st.text_input("Exit Note")
                if st.form_submit_button("✅ Close Trade"):
                    ok, pnl = close_trade(close_id, exit_price, close_note)
                    if ok:
                        st.success(f"{'✅' if pnl >= 0 else '❌'} Closed! P&L: ₹{pnl:+.2f}")
                    else:
                        st.error(str(pnl))
        else:
            st.info("No open trades to close.")

    with j_col2:
        st.markdown("#### 📋 All Trades")
        if st.button("🔄 Update Current Prices"):
            with st.spinner("Fetching..."):
                journal = update_open_prices()
        journal = load_journal()
        if journal.empty:
            st.info("No trades yet.")
        else:
            def style_journal(df):
                s = pd.DataFrame("", index=df.index, columns=df.columns)
                for i, row in df.iterrows():
                    if "status" in df.columns:
                        s.at[i,"status"] = "color:#00ff88;font-weight:700" if row["status"]=="OPEN" else "color:#4a5568"
                    for col in ["pnl","pnl_pct"]:
                        if col in df.columns and pd.notna(row.get(col)):
                            s.at[i,col] = "color:#00ff88;font-weight:700" if float(row[col]) >= 0 else "color:#ff4d6d;font-weight:700"
                return s
            st.dataframe(
                journal.style.apply(style_journal, axis=None).format({
                    "entry_price": "₹{:.2f}", "stop_loss": "₹{:.2f}",
                    "target_1": "₹{:.2f}", "target_2": "₹{:.2f}",
                    "exit_price": lambda x: f"₹{x:.2f}" if pd.notna(x) else "—",
                    "pnl":        lambda x: f"₹{x:+.2f}" if pd.notna(x) else "—",
                    "pnl_pct":    lambda x: f"{x:+.2f}%" if pd.notna(x) else "—",
                }, na_rep="—"),
                use_container_width=True, height=500
            )

# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — P&L TRACKER
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 💰 P&L Tracker")
    summary = get_summary()
    journal = update_open_prices() if not load_journal().empty else pd.DataFrame()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Trades",  summary["total"],  f'{summary["open"]} open')
    c2.metric("Closed",        summary["closed"])
    c3.metric("Total P&L",    f'₹{summary["total_pnl"]:+.2f}', "realised")
    c4.metric("Win Rate",      f'{summary["win_rate"]}%')
    c5.metric("Avg P&L",      f'₹{summary["avg_pnl"]:+.2f}', "per trade")
    st.markdown("<br>", unsafe_allow_html=True)

    if not journal.empty:
        closed = journal[journal["status"] == "CLOSED"].copy()
        open_t = journal[journal["status"] == "OPEN"].copy()
        pc_l, pc_r = st.columns(2)

        with pc_l:
            st.markdown("#### 🟢 Open Positions")
            if open_t.empty:
                st.info("No open positions.")
            else:
                for _, row in open_t.iterrows():
                    pnl     = float(row.get("pnl") or 0)
                    pnl_pct = float(row.get("pnl_pct") or 0)
                    pnl_col = "#00ff88" if pnl >= 0 else "#ff4d6d"
                    ep      = float(row["entry_price"])
                    sl      = float(row["stop_loss"])
                    t2      = float(row["target_2"])
                    sl_dist = round((ep - sl) / ep * 100, 1)
                    t2_dist = round((t2 - ep) / ep * 100, 1)
                    card(
                        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                        f'<div><span style="font-family:Syne,sans-serif;font-size:16px;font-weight:800;color:#00ff88">'
                        f'#{int(row["id"])} {row["symbol"]}</span>'
                        f'<span style="font-size:10px;color:#2d6b2d;margin-left:8px">'
                        f'{row["entry_date"]} · {int(row["quantity"])} shares</span></div>'
                        f'<div style="text-align:right">'
                        f'<div style="font-size:16px;font-weight:700;color:{pnl_col}">&#8377;{pnl:+.2f}</div>'
                        f'<div style="font-size:11px;color:{pnl_col}">{pnl_pct:+.2f}%</div>'
                        f'</div></div>'
                        f'<div style="font-size:11px;color:#2d6b2d">'
                        f'Entry <b style="color:#38bdf8">&#8377;{ep}</b> &nbsp; '
                        f'Stop <b style="color:#ff4d6d">&#8377;{sl} (-{sl_dist}%)</b> &nbsp; '
                        f'T2 <b style="color:#00ff88">&#8377;{t2} (+{t2_dist}%)</b>'
                        f'</div>'
                    )

        with pc_r:
            st.markdown("#### 📈 P&L History")
            if closed.empty:
                st.info("No closed trades yet.")
            else:
                closed = closed.sort_values("exit_date")
                closed["cumulative_pnl"] = closed["pnl"].cumsum()
                fig_pnl = go.Figure()
                fig_pnl.add_trace(go.Bar(
                    x=closed["symbol"] + " #" + closed["id"].astype(str),
                    y=closed["pnl"], name="Trade P&L",
                    marker_color=["rgba(0,255,136,0.7)" if p >= 0 else "rgba(255,77,109,0.7)"
                                  for p in closed["pnl"]],
                ))
                fig_pnl.add_trace(go.Scatter(
                    x=closed["symbol"] + " #" + closed["id"].astype(str),
                    y=closed["cumulative_pnl"], name="Cumulative P&L",
                    line=dict(color="#00ff88", width=2), yaxis="y2"
                ))
                fig_pnl.update_layout(
                    height=300, paper_bgcolor="#060d06", plot_bgcolor="#0a130a",
                    font=dict(family="JetBrains Mono", color="#b8f5b8", size=10),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=10, r=60, t=20, b=40),
                    yaxis=dict(gridcolor="#1a2e1a", title="Trade P&L ₹"),
                    yaxis2=dict(overlaying="y", side="right", title="Cumulative ₹",
                                gridcolor="rgba(0,0,0,0)"),
                    xaxis=dict(gridcolor="#1a2e1a"),
                )
                st.plotly_chart(fig_pnl, use_container_width=True,
                                config={"displayModeBar": False})
    else:
        st.info("Log some trades to see P&L tracking.")

st.markdown("""
<div class="footer">
    Live data via Yahoo Finance · NSE India · MACD · Bollinger · ATR · EMA<br>
    ⚠️ Not financial advice. Educational use only.
</div>
""", unsafe_allow_html=True)
