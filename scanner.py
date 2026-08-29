import os
import time
import requests
import ccxt
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
]

TIMEFRAMES = ["15m", "1h"]

SCAN_SECONDS = 60
MAX_SIGNALS_PER_DAY = 4
MIN_RR = 2.0

exchange = ccxt.bitget({
    "enableRateLimit": True,
})

sent_signals = set()
daily_signals = 0
current_day = None


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=20
    )
    r.raise_for_status()


def get_candles(symbol, timeframe):
    return exchange.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        limit=300
    )


def atr(candles, period=14):
    trs = []

    for i in range(1, len(candles)):
        high = candles[i][2]
        low = candles[i][3]
        previous_close = candles[i - 1][4]

        trs.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close)
            )
        )

    if len(trs) < period:
        return 0

    return sum(trs[-period:]) / period


def swing_high(candles, i, strength=3):
    if i < strength or i >= len(candles) - strength:
        return False

    value = candles[i][2]

    for j in range(1, strength + 1):
        if value <= candles[i-j][2]:
            return False
        if value <= candles[i+j][2]:
            return False

    return True


def swing_low(candles, i, strength=3):
    if i < strength or i >= len(candles) - strength:
        return False

    value = candles[i][3]

    for j in range(1, strength + 1):
        if value >= candles[i-j][3]:
            return False
        if value >= candles[i+j][3]:
            return False

    return True


def detect_choch(candles):

    if len(candles) < 100:
        return None

    data = candles[-180:]

    highs = []
    lows = []

    for i in range(5, len(data) - 5):

        if swing_high(data, i):
            highs.append(i)

        if swing_low(data, i):
            lows.append(i)

    if len(highs) < 2 or len(lows) < 2:
        return None

    last_high = highs[-1]
    previous_high = highs[-2]

    last_low = lows[-1]
    previous_low = lows[-2]

    price = data[-1][4]

    # ==========================
    # BULLISH TREND → CHOCH DOWN
    # ==========================

    bullish = (
        data[last_high][2] > data[previous_high][2]
        and
        data[last_low][3] > data[previous_low][3]
    )

    if bullish:

        choch_level = data[last_low][3]

        # قیمت باید واقعاً ساختار را بشکند
        if price < choch_level:

            low = data[previous_low][3]
            high = data[last_high][2]

            rng = high - low

            if rng <= 0:
                return None

            # Fib retracement zone
            entry1 = high - rng * 0.786
            entry2 = high - rng * 0.83

            # برای SHORT باید قیمت زیر Entry نباشد
            if price < min(entry1, entry2):
                return None

            # برای SHORT باید قیمت داخل یا نزدیک Zone باشد
            zone_low = min(entry1, entry2)
            zone_high = max(entry1, entry2)

            tolerance = max(
                atr(data) * 0.15,
                price * 0.0005
            )

            if price > zone_high + tolerance:
                return None

            sl = high
            tp = low

            risk = sl - price
            reward = price - tp

            if risk <= 0 or reward <= 0:
                return None

            rr = reward / risk

            if rr < MIN_RR:
                return None

            return {
                "side": "SHORT",
                "entry1": entry1,
                "entry2": entry2,
                "sl": sl,
                "tp": tp,
                "rr": rr
            }

    # ==========================
    # BEARISH TREND → CHOCH UP
    # ==========================

    bearish = (
        data[last_low][3] < data[previous_low][3]
        and
        data[last_high][2] < data[previous_high][2]
    )

    if bearish:

        choch_level = data[last_high][2]

        if price > choch_level:

            high = data[previous_high][2]
            low = data[last_low][3]

            rng = high - low

            if rng <= 0:
                return None

            entry1 = low + rng * 0.786
            entry2 = low + rng * 0.83

            # برای LONG قیمت نباید بالاتر از Zone باشد
            if price > max(entry1, entry2):
                return None

            zone_low = min(entry1, entry2)
            zone_high = max(entry1, entry2)

            tolerance = max(
                atr(data) * 0.15,
                price * 0.0005
            )

            if price < zone_low - tolerance:
                return None

            sl = low
            tp = high

            risk = price - sl
            reward = tp - price

            if risk <= 0 or reward <= 0:
                return None

            rr = reward / risk

            if rr < MIN_RR:
                return None

            return {
                "side": "LONG",
                "entry1": entry1,
                "entry2": entry2,
                "sl": sl,
                "tp": tp,
                "rr": rr
            }

    return None


def scan():

    global daily_signals
    global current_day

    today = time.strftime("%Y-%m-%d")

    if current_day != today:
        current_day = today
        daily_signals = 0
        sent_signals.clear()

    print("\n==============================")
    print("SIGNABOT LIVE SCAN")
    print("==============================")

    for symbol in SYMBOLS:

        for timeframe in TIMEFRAMES:

            try:

                candles = get_candles(
                    symbol,
                    timeframe
                )

                price = candles[-1][4]

                signal = detect_choch(candles)

                if signal is None:

                    print(
                        f"[NO VALID SIGNAL] "
                        f"{symbol} {timeframe} "
                        f"PRICE={price}",
                        flush=True
                    )

                    continue

                print(
                    f"[VALID CHOCH] "
                    f"{symbol} {timeframe} "
                    f"{signal['side']} "
                    f"PRICE={price} "
                    f"ENTRY1={signal['entry1']} "
                    f"ENTRY2={signal['entry2']} "
                    f"RR={signal['rr']:.2f}",
                    flush=True
                )

                if daily_signals >= MAX_SIGNALS_PER_DAY:
                    print(
                        "[DAILY LIMIT REACHED]",
                        flush=True
                    )
                    continue

                key = (
                    symbol,
                    timeframe,
                    signal["side"],
                    round(signal["entry1"], 4)
                )

                if key in sent_signals:
                    continue

                sent_signals.add(key)
                daily_signals += 1

                message = f"""
🚨 SIGNABOT — VALID CHOCH SIGNAL

━━━━━━━━━━━━━━━━
{symbol}
TIMEFRAME: {timeframe}
━━━━━━━━━━━━━━━━

📌 DIRECTION:
{signal['side']}

💰 CURRENT:
{price:.6f}

🎯 ENTRY 1:
{signal['entry1']:.6f}

🎯 ENTRY 2:
{signal['entry2']:.6f}

🛑 STOP LOSS:
{signal['sl']:.6f}

🎯 TARGET:
{signal['tp']:.6f}

📊 RISK / REWARD:
1 : {signal['rr']:.2f}

📐 FIB:
0 → 0.66 → 0.70 → 0.786 → 0.83 → 1

📊 STRUCTURE:
TREND → SWING → CHOCH → PULLBACK

⚠️ MANUAL TRADE ONLY
⚠️ AUTO TRADE: OFF
"""

                send_telegram(message)

                print(
                    "🚨 TELEGRAM SIGNAL SENT",
                    flush=True
                )

            except Exception as e:

                print(
                    f"SCAN ERROR "
                    f"{symbol} {timeframe}: {repr(e)}",
                    flush=True
                )


print("================================")
print("SIGNABOT LIVE ENGINE STARTED")
print("================================")
print("Exchange : BITGET")
print("Mode     : SIGNAL ONLY")
print("AutoTrade: OFF")
print("Max Daily Signals: 4")
print("Minimum RR: 1:2")
print("================================")

while True:

    try:
        scan()

    except Exception as e:
        print(
            f"ENGINE ERROR: {repr(e)}",
            flush=True
        )

    time.sleep(SCAN_SECONDS)
