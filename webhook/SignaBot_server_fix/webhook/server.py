import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

@app.get("/")
def home():
    return jsonify({"service": "SignaBot TradingView Webhook", "status": "online"})

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/telegram-test")
def telegram_test():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return jsonify({"ok": False, "error": "Telegram environment variables missing"}), 500
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=20)
        result = r.json()
        if not result.get("ok"):
            return jsonify({"ok": False, "telegram": result}), 502
        msg = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": "SignaBot Telegram connection test successful."},
            timeout=20
        )
        msg_result = msg.json()
        print("TELEGRAM TEST RESPONSE:", msg_result, flush=True)
        if not msg_result.get("ok"):
            return jsonify({"ok": False, "telegram": msg_result}), 502
        return jsonify({"ok": True, "telegram": "connected", "message_sent": True})
    except requests.RequestException as exc:
        print("TELEGRAM CONNECTION ERROR:", repr(exc), flush=True)
        return jsonify({"ok": False, "error": "telegram_connection_failed", "detail": str(exc)}), 502

@app.post("/webhook/<secret>")
def tradingview_webhook(secret):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True)
    if data is None:
        raw = request.get_data(as_text=True)
        print("INVALID JSON. RAW BODY:", raw, flush=True)
        return jsonify({"error": "invalid_json"}), 400
    print("WEBHOOK RECEIVED:", data, flush=True)
    text = (
        "TRADINGVIEW SIGNAL\n\n"
        f"COIN: {data.get('symbol','')}\n"
        f"SIDE: {data.get('direction','')}\n"
        f"TIMEFRAME: {data.get('timeframe','')}\n"
        f"STRATEGY: {data.get('strategy','')}\n"
        f"SCORE: {data.get('score','')}/100\n\n"
        f"PRICE: {data.get('price','')}\n"
        f"ENTRY 1: {data.get('entry1','')}\n"
        f"ENTRY 2: {data.get('entry2','')}\n"
        f"SL: {data.get('stop','')}\n"
        f"TP1: {data.get('tp1','')}\n"
        f"TP2: {data.get('tp2','')}\n"
        f"TP3: {data.get('tp3','')}"
    )
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=20
        )
        result = r.json()
        print("TELEGRAM RESPONSE:", result, flush=True)
        if not result.get("ok"):
            return jsonify({"error": "telegram_failed", "telegram": result}), 502
    except requests.RequestException as exc:
        print("TELEGRAM CONNECTION ERROR:", repr(exc), flush=True)
        return jsonify({"error": "telegram_connection_failed", "detail": str(exc)}), 502
    return jsonify({"status": "received", "telegram": "sent"})
