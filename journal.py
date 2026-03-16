"""
journal.py — Trade journal: log entries, track open trades, calculate P&L
Saves to trades.csv in the same folder.
"""
import pandas as pd
import os
from datetime import datetime

JOURNAL_FILE = "trades.csv"

COLUMNS = [
    "id", "symbol", "entry_date", "entry_price", "stop_loss",
    "target_1", "target_2", "quantity", "status",
    "exit_date", "exit_price", "pnl", "pnl_pct", "notes"
]


def load_journal():
    if os.path.exists(JOURNAL_FILE):
        df = pd.read_csv(JOURNAL_FILE)
        # Ensure all columns exist (in case file is old)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=COLUMNS)


def save_journal(df):
    df.to_csv(JOURNAL_FILE, index=False)


def add_trade(symbol, entry_price, stop_loss, target_1, target_2, quantity, notes=""):
    df  = load_journal()
    new_id = int(df["id"].max()) + 1 if len(df) > 0 else 1
    new_row = {
        "id":           new_id,
        "symbol":       symbol.upper(),
        "entry_date":   datetime.now().strftime("%Y-%m-%d"),
        "entry_price":  round(entry_price, 2),
        "stop_loss":    round(stop_loss, 2),
        "target_1":     round(target_1, 2),
        "target_2":     round(target_2, 2),
        "quantity":     int(quantity),
        "status":       "OPEN",
        "exit_date":    None,
        "exit_price":   None,
        "pnl":          None,
        "pnl_pct":      None,
        "notes":        notes,
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_journal(df)
    return new_id


def close_trade(trade_id, exit_price, notes=""):
    df  = load_journal()
    idx = df[df["id"] == trade_id].index
    if len(idx) == 0:
        return False, "Trade not found"

    i   = idx[0]
    entry_price = float(df.at[i, "entry_price"])
    quantity    = int(df.at[i, "quantity"])
    pnl         = round((exit_price - entry_price) * quantity, 2)
    pnl_pct     = round((exit_price - entry_price) / entry_price * 100, 2)

    df.at[i, "status"]     = "CLOSED"
    df.at[i, "exit_date"]  = datetime.now().strftime("%Y-%m-%d")
    df.at[i, "exit_price"] = round(exit_price, 2)
    df.at[i, "pnl"]        = pnl
    df.at[i, "pnl_pct"]    = pnl_pct
    if notes:
        df.at[i, "notes"]  = notes

    save_journal(df)
    return True, pnl


def get_summary():
    df = load_journal()
    if df.empty:
        return {"total": 0, "open": 0, "closed": 0, "total_pnl": 0, "win_rate": 0, "avg_pnl": 0}

    closed = df[df["status"] == "CLOSED"]
    open_t = df[df["status"] == "OPEN"]

    total_pnl = round(float(closed["pnl"].sum()) if len(closed) > 0 else 0, 2)
    winners   = len(closed[closed["pnl"] > 0]) if len(closed) > 0 else 0
    win_rate  = round(winners / len(closed) * 100, 1) if len(closed) > 0 else 0
    avg_pnl   = round(float(closed["pnl"].mean()) if len(closed) > 0 else 0, 2)

    return {
        "total":     len(df),
        "open":      len(open_t),
        "closed":    len(closed),
        "total_pnl": total_pnl,
        "win_rate":  win_rate,
        "avg_pnl":   avg_pnl,
    }


def update_open_prices():
    """Fetches current prices for all open trades and returns updated df."""
    import yfinance as yf
    import time
    df = load_journal()
    open_trades = df[df["status"] == "OPEN"]
    if open_trades.empty:
        return df

    for idx, row in open_trades.iterrows():
        try:
            time.sleep(0.5)
            ticker = yf.Ticker(str(row["symbol"]) + ".NS")
            hist   = ticker.history(period="2d")
            if not hist.empty:
                current = round(float(hist["Close"].iloc[-1]), 2)
                entry   = float(row["entry_price"])
                qty     = int(row["quantity"])
                df.at[idx, "exit_price"] = current   # store as "current price"
                df.at[idx, "pnl"]        = round((current - entry) * qty, 2)
                df.at[idx, "pnl_pct"]    = round((current - entry) / entry * 100, 2)
        except:
            continue

    return df
