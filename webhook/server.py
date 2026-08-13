import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

@app.get("/")
def home():
    return jsonify({"service":"SignaBot TradingView Webhook","status":"online"}), 200

@app.get("/health")
def health():
    return jsonify({"status":"ok"}), 200

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Telegram environment variables are not configured")
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=15
    )
    r.raise_for_status()

def build_message(d):
    return (
        "🚨 TRADINGVIEW SIGNAL\n\n"
        f"COIN: {d.get('symbol','')}\n"
        f"SIDE: {d.get('direction','')}\n"
        f"TIMEFRAME: {d.get('timeframe','')}\n"
        f"STRATEGY: {d.get('strategy','')}\n"
        f"SCORE: {d.get('score','')}/100\n\n"
        f"PRICE: {d.get('price','')}\n"
        f"ENTRY 1: {d.get('entry1','')}\n"
        f"ENTRY 2: {d.get('entry2','')}\n"
        f"SL: {d.get('stop','')}\n"
        f"TP1: {d.get('tp1','')}\n"
        f"TP2: {d.get('tp2','')}\n"
        f"TP3: {d.get('tp3','')}"
    )

@app.post("/webhook/<secret>")
def tradingview_webhook(secret):
    if not SECRET or secret != SECRET:
        return jsonify({"error":"unauthorized"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error":"invalid_json"}), 400
    print("WEBHOOK RECEIVED:", data, flush=True)
    try:
        send_telegram(build_message(data))
    except Exception as exc:
        print("TELEGRAM ERROR:", repr(exc), flush=True)
        return jsonify({"error":"telegram_failed"}), 502
    return jsonify({"status":"received"}), 200
