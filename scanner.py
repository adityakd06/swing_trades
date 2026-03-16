"""
scanner.py — Scans NSE stocks and ranks them by swing trade setup quality
"""
import pandas as pd
import yfinance as yf
import time
from indicators import calc_swing_setup, calc_support_resistance

NSE_UNIVERSE = [
    # Large caps
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","HINDUNILVR","ITC","SBIN",
    "BAJFINANCE","BHARTIARTL","KOTAKBANK","LT","AXISBANK","ASIANPAINT","MARUTI",
    "TITAN","SUNPHARMA","ULTRACEMCO","WIPRO","HCLTECH","TATAMOTORS","ONGC",
    "POWERGRID","NTPC","COALINDIA","BPCL","GAIL","HINDALCO","JSWSTEEL","TATASTEEL",
    # Mid caps
    "BANKBARODA","PNB","CANBK","SAIL","NMDC","NHPC","IRFC","NBCC","SJVN",
    "RVNL","BEL","HAL","BHEL","IRCON","IDFCFIRSTB","FEDERALBNK","INDUSINDBK",
    "MOTHERSON","BALKRISIND","TVSMOTOR","HEROMOTOCO","BAJAJ-AUTO",
    "DIVISLAB","DRREDDY","CIPLA","APOLLOHOSP","MAXHEALTH",
    "PIDILITIND","BERGEPAINT","HAVELLS","VOLTAS","WHIRLPOOL",
    # Small caps / ₹100 range
    "YESBANK","IDEA","JPPOWER","RPOWER","NFL","IFCI","NTPCGREEN","UJJIVANSFB",
]


def scan_stocks(symbols=None, max_stocks=40):
    """
    Scans stocks, calculates swing setup for each, returns ranked DataFrame.
    """
    if symbols is None:
        symbols = NSE_UNIVERSE

    results = []

    for i, symbol in enumerate(symbols[:max_stocks]):
        try:
            time.sleep(0.8)
            ticker = yf.Ticker(symbol + ".NS")
            data   = ticker.history(period="6mo", interval="1d")

            if data.empty or len(data) < 60:
                continue

            setup = calc_swing_setup(data)

            # Skip poor setups
            if setup["score"] < 20:
                continue

            support, resistance = calc_support_resistance(data)

            price    = setup["price"]
            pchange  = round((price - float(data["Close"].iloc[-2])) / float(data["Close"].iloc[-2]) * 100, 2)
            volume   = int(data["Volume"].iloc[-1])
            avg_vol  = int(data["Volume"].rolling(20).mean().iloc[-1])
            vol_ratio= round(volume / avg_vol, 2) if avg_vol > 0 else 1

            results.append({
                "Symbol":      symbol,
                "Price ₹":     price,
                "Change %":    pchange,
                "Score":       setup["score"],
                "Quality":     setup["quality"],
                "Entry ₹":     setup["entry"],
                "Stop Loss ₹": setup["stop_loss"],
                "Target 1 ₹":  setup["target_1"],
                "Target 2 ₹":  setup["target_2"],
                "R:R Ratio":   setup["rr_ratio"],
                "RSI":         setup["rsi"],
                "MACD":        setup["macd"],
                "EMA20":       setup["ema20"],
                "EMA50":       setup["ema50"],
                "ATR":         setup["atr"],
                "Vol Ratio":   vol_ratio,
                "Support":     support[0] if support else None,
                "Resistance":  resistance[0] if resistance else None,
                "_reasons":    setup["reasons"],
                "_quality_color": setup["quality_color"],
                "_volume":     volume,
            })

        except Exception as e:
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("Score", ascending=False)
    return df
