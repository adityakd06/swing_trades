"""
indicators.py — All technical indicators for the swing trader
Includes: MA, EMA, RSI, MACD, Bollinger Bands, Support/Resistance, ATR
"""
import pandas as pd
import numpy as np


def calc_rsi(series, period=14):
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast   = series.ewm(span=fast, adjust=False).mean()
    ema_slow   = series.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line= macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(series, period=20, std=2):
    ma     = series.rolling(period).mean()
    stddev = series.rolling(period).std()
    upper  = ma + std * stddev
    lower  = ma - std * stddev
    bw     = (upper - lower) / ma * 100       # Bandwidth %
    pct_b  = (series - lower) / (upper - lower)  # %B position
    return upper, ma, lower, bw, pct_b


def calc_atr(high, low, close, period=14):
    """Average True Range — measures volatility. Used for stop-loss calculation."""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_support_resistance(data, lookback=20, n_levels=3):
    """
    Finds support and resistance levels using recent swing highs/lows.
    A swing high = local peak; swing low = local trough.
    """
    highs  = data["High"].rolling(lookback, center=True).max()
    lows   = data["Low"].rolling(lookback, center=True).min()

    # Swing highs: where price == rolling max
    swing_highs = data["High"][data["High"] == highs].dropna().tail(10)
    swing_lows  = data["Low"][data["Low"]   == lows].dropna().tail(10)

    resistance = sorted(swing_highs.values, reverse=True)[:n_levels]
    support    = sorted(swing_lows.values)[:n_levels]

    return support, resistance


def calc_swing_setup(data):
    """
    Core swing trade setup calculator.
    Returns entry, stop-loss, target, risk/reward, and signal quality.

    Strategy:
      - Uses MACD crossover + RSI zone + Bollinger Band position
      - Entry = current close
      - Stop  = Entry - 1.5x ATR  (dynamic, volatility-adjusted)
      - Target= Entry + 3.0x ATR  (2:1 reward-to-risk minimum)
    """
    close  = data["Close"]
    high   = data["High"]
    low    = data["Low"]

    # Indicators
    rsi                       = calc_rsi(close)
    macd, macd_sig, macd_hist = calc_macd(close)
    bb_up, bb_mid, bb_low, bw, pct_b = calc_bollinger(close)
    atr                       = calc_atr(high, low, close)
    ema20                     = close.ewm(span=20, adjust=False).mean()
    ema50                     = close.ewm(span=50, adjust=False).mean()

    latest      = data.iloc[-1]
    prev        = data.iloc[-2]
    price       = round(float(close.iloc[-1]), 2)
    atr_val     = round(float(atr.iloc[-1]), 2)
    rsi_val     = round(float(rsi.iloc[-1]), 1)
    macd_val    = round(float(macd.iloc[-1]), 3)
    macd_s_val  = round(float(macd_sig.iloc[-1]), 3)
    macd_h_val  = round(float(macd_hist.iloc[-1]), 3)
    macd_h_prev = round(float(macd_hist.iloc[-2]), 3)
    pct_b_val   = round(float(pct_b.iloc[-1]), 2)
    bb_up_val   = round(float(bb_up.iloc[-1]), 2)
    bb_low_val  = round(float(bb_low.iloc[-1]), 2)
    ema20_val   = round(float(ema20.iloc[-1]), 2)
    ema50_val   = round(float(ema50.iloc[-1]), 2)

    # ── Signal scoring (0–100) ────────────────────────────────────────────────
    score = 0
    reasons = []

    # 1. MACD bullish crossover or rising histogram
    macd_bullish = macd_val > macd_s_val
    macd_rising  = macd_h_val > macd_h_prev
    if macd_bullish and macd_rising:
        score += 30
        reasons.append("MACD bullish crossover + rising histogram")
    elif macd_bullish:
        score += 15
        reasons.append("MACD above signal line")

    # 2. RSI in sweet spot (40–65 = momentum without being overbought)
    if 40 <= rsi_val <= 65:
        score += 25
        reasons.append(f"RSI {rsi_val} in ideal swing zone (40–65)")
    elif rsi_val < 40:
        score += 10
        reasons.append(f"RSI {rsi_val} recovering from oversold")

    # 3. Price above EMA20 (short-term trend)
    if price > ema20_val:
        score += 20
        reasons.append("Price above EMA20 — short-term uptrend")

    # 4. EMA20 above EMA50 (medium-term trend confirmation)
    if ema20_val > ema50_val:
        score += 15
        reasons.append("EMA20 > EMA50 — medium-term trend bullish")

    # 5. Bollinger position (near lower band = oversold pullback = entry opportunity)
    if pct_b_val < 0.3:
        score += 10
        reasons.append("Near Bollinger lower band — pullback entry")

    # ── Entry / Stop / Target ─────────────────────────────────────────────────
    entry      = price
    stop_loss  = round(entry - 1.5 * atr_val, 2)
    target_1   = round(entry + 2.0 * atr_val, 2)   # Conservative target
    target_2   = round(entry + 3.0 * atr_val, 2)   # Full target
    risk       = round(entry - stop_loss, 2)
    reward     = round(target_2 - entry, 2)
    rr_ratio   = round(reward / risk, 2) if risk > 0 else 0

    # ── Setup quality ─────────────────────────────────────────────────────────
    if score >= 70:
        quality = "A+ Setup 🔥"
        quality_color = "#00e896"
    elif score >= 50:
        quality = "B Setup ✅"
        quality_color = "#38bdf8"
    elif score >= 30:
        quality = "C Setup ⚠️"
        quality_color = "#f59e0b"
    else:
        quality = "No Setup ❌"
        quality_color = "#ff4d6d"

    return {
        "price":         price,
        "entry":         entry,
        "stop_loss":     stop_loss,
        "target_1":      target_1,
        "target_2":      target_2,
        "risk":          risk,
        "reward":        reward,
        "rr_ratio":      rr_ratio,
        "atr":           atr_val,
        "rsi":           rsi_val,
        "macd":          macd_val,
        "macd_signal":   macd_s_val,
        "macd_hist":     macd_h_val,
        "ema20":         ema20_val,
        "ema50":         ema50_val,
        "bb_upper":      bb_up_val,
        "bb_lower":      bb_low_val,
        "pct_b":         pct_b_val,
        "score":         score,
        "quality":       quality,
        "quality_color": quality_color,
        "reasons":       reasons,
        "macd_series":   macd,
        "macd_sig_series": macd_sig,
        "macd_hist_series": macd_hist,
        "rsi_series":    rsi,
        "bb_upper_series": bb_up,
        "bb_lower_series": bb_low,
        "bb_mid_series": bb_mid,
        "ema20_series":  ema20,
        "ema50_series":  ema50,
    }


def calc_holding_period(data, setup):
    """
    Estimates the ideal holding period for a swing trade.

    Logic:
      - ATR tells us how much the stock moves per day on average
      - Distance to target / daily ATR = minimum days needed to reach target
      - Trend strength (EMA gap) and MACD momentum adjust this up or down
      - Volatility regime (high/low ATR%) adjusts further
    """
    price     = setup["price"]
    atr       = setup["atr"]
    target_2  = setup["target_2"]
    rsi       = setup["rsi"]
    macd_hist = setup["macd_hist"]
    ema20     = setup["ema20"]
    ema50     = setup["ema50"]

    atr_pct     = (atr / price) * 100
    target_dist = target_2 - price
    base_days   = max(3, round(target_dist / atr)) if atr > 0 else 10

    adjustment = 0
    reasoning  = []

    # MACD momentum
    if macd_hist > 0:
        adjustment -= 2
        reasoning.append("MACD histogram positive — momentum accelerating, faster move expected")
    else:
        adjustment += 3
        reasoning.append("MACD histogram negative — momentum building, needs more time")

    # RSI zone
    if 45 <= rsi <= 60:
        adjustment -= 1
        reasoning.append(f"RSI {rsi} in ideal momentum zone — trend likely to continue steadily")
    elif rsi < 40:
        adjustment += 4
        reasoning.append(f"RSI {rsi} recovering — stock needs time to build momentum")
    elif rsi > 65:
        adjustment -= 2
        reasoning.append(f"RSI {rsi} already strong — may reach target faster, watch for reversal")

    # EMA trend alignment
    if ema20 > ema50:
        adjustment -= 1
        reasoning.append("EMA20 > EMA50 — medium-term trend aligned, supports quicker move")
    else:
        adjustment += 2
        reasoning.append("EMA20 < EMA50 — fighting medium-term trend, may take longer")

    # Volatility regime
    if atr_pct > 3:
        adjustment -= 2
        reasoning.append(f"High volatility (ATR {atr_pct:.1f}%) — stock moves fast, shorter hold")
    elif atr_pct < 1.5:
        adjustment += 3
        reasoning.append(f"Low volatility (ATR {atr_pct:.1f}%) — slow mover, patience needed")
    else:
        reasoning.append(f"Normal volatility (ATR {atr_pct:.1f}%)")

    ideal_days = max(3, base_days + adjustment)
    min_days   = max(2, ideal_days - 3)
    max_days   = ideal_days + 7

    if ideal_days <= 5:
        label    = f"{ideal_days} trading days (~1 week)"
        category = "Very Short Swing"
        cat_color= "#38bdf8"
    elif ideal_days <= 10:
        label    = f"{ideal_days} trading days (~{round(ideal_days/5)} weeks)"
        category = "Short Swing"
        cat_color= "#00ff88"
    elif ideal_days <= 20:
        label    = f"{ideal_days} trading days (~{round(ideal_days/5)} weeks)"
        category = "Medium Swing"
        cat_color= "#f59e0b"
    else:
        months   = round(ideal_days / 21)
        label    = f"{ideal_days} trading days (~{months} month{'s' if months>1 else ''})"
        category = "Long Swing / Positional"
        cat_color= "#a78bfa"

    exit_rules = [
        f"✅ Book partial profit at Target 1 (₹{setup['target_1']}) — sell 50% of position",
        f"🚀 Let remaining 50% run to Target 2 (₹{setup['target_2']})",
        f"🛑 Exit 100% if price closes BELOW Stop Loss (₹{setup['stop_loss']})",
        f"⏰ Time stop: exit if Target 2 not hit within {max_days} trading days",
        f"📉 Exit early if RSI drops below 35 before hitting target — momentum lost",
    ]

    return {
        "ideal_days": ideal_days,
        "min_days":   min_days,
        "max_days":   max_days,
        "label":      label,
        "category":   category,
        "cat_color":  cat_color,
        "atr_pct":    round(atr_pct, 2),
        "reasoning":  reasoning,
        "exit_rules": exit_rules,
    }
