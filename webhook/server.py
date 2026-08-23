import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

def tg(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT, "text": text},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

@app.get("/")
def home():
    return jsonify({"service": "SignaBot Webhook", "status": "online"})

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/telegram-test")
def telegram_test():
    return jsonify({"ok": tg("✅ SignaBot Telegram connection test successful.")["ok"]})

@app.post("/webhook/<secret>")
def webhook(secret):
    if not SECRET or secret != SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "invalid_json"}), 400
    tg("🚨 TRADINGVIEW SIGNAL\n\n" + "\n".join(f"{k}: {v}" for k, v in data.items()))
    return jsonify({"status": "received", "telegram": "sent"})
