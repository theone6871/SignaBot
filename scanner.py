import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SYMBOLS = [x.strip().upper() for x in os.getenv("SIGNAL_SYMBOLS", "BTCUSDT").split(",") if x.strip()]
TIMEFRAMES = [x.strip() for x in os.getenv("SIGNAL_TIMEFRAMES", "15m,1h").split(",") if x.strip()]
BASE = "https://data-api.binance.vision"
sent = set()

def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT, "text": text},
        timeout=20,
    )
    r.raise_for_status()

def candles(symbol, tf, limit=300):
    r = requests.get(
        f"{BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": tf, "limit": limit},
        timeout=20,
    )
    r.raise_for_status()
    return [{"h": float(x[2]), "l": float(x[3]), "c": float(x[4])} for x in r.json()]

def atr(c, n=14):
    tr = []
    for i in range(1, len(c)):
        tr.append(max(c[i]["h"]-c[i]["l"], abs(c[i]["h"]-c[i-1]["c"]), abs(c[i]["c"]-c[i-1]["c"])))
    return sum(tr[-n:]) / min(n, len(tr)) if tr else 0

def detect(c):
    if len(c) < 80:
        return None
    w = c[-160:]
    a = atr(w)
    if a <= 0:
        return None
    first = sum(x["c"] for x in w[:5]) / 5
    last = sum(x["c"] for x in w[-5:]) / 5

    if last - first > 1.2*a:
        ei = max(range(len(w)), key=lambda i: w[i]["h"])
        if ei < 15 or ei > len(w)-5:
            return None
        si = min(range(max(0, ei-60), ei), key=lambda i: w[i]["l"])
        lo, hi = w[si]["l"], w[ei]["h"]
        rng = hi - lo
        pb = min(x["l"] for x in w[ei+1:])
        if rng <= 0 or hi - pb < 0.25*rng:
            return None
        if not any(x["c"] < lo + 0.66*rng for x in w[ei+1:]):
            return None
        levels = {k: hi - rng*k for k in [0, .66, .70, .786, .83, 1]}
        return "SHORT", levels[.786], levels[.83], hi, lo

    if first - last > 1.2*a:
        ei = min(range(len(w)), key=lambda i: w[i]["l"])
        if ei < 15 or ei > len(w)-5:
            return None
        si = max(range(max(0, ei-60), ei), key=lambda i: w[i]["h"])
        hi, lo = w[si]["h"], w[ei]["l"]
        rng = hi - lo
        pb = max(x["h"] for x in w[ei+1:])
        if rng <= 0 or pb - lo < 0.25*rng:
            return None
        if not any(x["c"] > hi - 0.66*rng for x in w[ei+1:]):
            return None
        levels = {k: lo + rng*k for k in [0, .66, .70, .786, .83, 1]}
        return "LONG", levels[.786], levels[.83], lo, hi

def main():
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                c = candles(symbol, tf)
                sig = detect(c)
                if not sig:
                    continue
                side, e1, e2, sl, tp = sig
                price = c[-1]["c"]
                tol = max(atr(c)*0.20, price*0.001)
                if min(abs(price-e1), abs(price-e2)) > tol:
                    continue
                key = f"{symbol}:{tf}:{side}:{round(e1,4)}"
                if key in sent:
                    continue
                sent.add(key)
                send(
                    f"🚨 CHOCH SIGNAL\n\n{symbol} | {tf}\n"
                    f"SIDE: {side}\nPRICE: {price}\n"
                    f"ENTRY 1: {e1:.6f}\nENTRY 2: {e2:.6f}\n"
                    f"SL: {sl:.6f}\nTP: {tp:.6f}\n\n"
                    f"Wave → extreme → pullback → structure change\n"
                    f"Fib: 0 / 0.66 / 0.70 / 0.786 / 0.83 / 1"
                )
            except Exception as e:
                print("SCAN ERROR", symbol, tf, repr(e), flush=True)

if __name__ == "__main__":
    main()
