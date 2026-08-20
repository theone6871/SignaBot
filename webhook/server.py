import os,time,threading,requests
from flask import Flask,request,jsonify
from dotenv import load_dotenv
load_dotenv()
app=Flask(__name__)
TOKEN=os.getenv("TELEGRAM_TOKEN","").strip()
CHAT=os.getenv("TELEGRAM_CHAT_ID","").strip()
SECRET=os.getenv("WEBHOOK_SECRET","").strip()
SYMBOLS=[x.strip().upper() for x in os.getenv("SIGNAL_SYMBOLS","BTCUSDT").split(",") if x.strip()]
TFS=[x.strip() for x in os.getenv("SIGNAL_TIMEFRAMES","15m,1h").split(",") if x.strip()]
BASE="https://data-api.binance.vision"
last_sent=set()

def tg(text):
    r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHAT,"text":text},timeout=20)
    r.raise_for_status(); return r.json()

def candles(symbol,tf,limit=300):
    r=requests.get(f"{BASE}/api/v3/klines",params={"symbol":symbol,"interval":tf,"limit":limit},timeout=20); r.raise_for_status()
    return [{"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4]),"t":x[0]} for x in r.json()]

def atr(c,n=14):
    tr=[]
    for i in range(1,len(c)):
        tr.append(max(c[i]["h"]-c[i]["l"],abs(c[i]["h"]-c[i-1]["c"]),abs(c[i]["l"]-c[i-1]["c"])))
    return sum(tr[-n:])/min(n,len(tr)) if tr else 0

def detect(c):
    if len(c)<80:return None
    a=atr(c)
    w=c[-160:]
    # Wave-based, not single-candle CHOCH: directional wave, extreme, pullback,
    # then structure break beyond the 0.66 retracement of that wave.
    first=sum(x["c"] for x in w[:5])/5; last=sum(x["c"] for x in w[-5:])/5
    if last-first>1.2*a:
        ei=max(range(len(w)),key=lambda i:w[i]["h"])
        if ei<15 or ei>len(w)-5:return None
        si=min(range(max(0,ei-60),ei),key=lambda i:w[i]["l"])
        lo,hi=w[si]["l"],w[ei]["h"]; rng=hi-lo
        pb=min(x["l"] for x in w[ei+1:])
        if pb>hi-.25*rng or not any(x["c"]<lo+.66*rng for x in w[ei+1:]):return None
        return make("SHORT",lo,hi,pb,a)
    if first-last>1.2*a:
        ei=min(range(len(w)),key=lambda i:w[i]["l"])
        if ei<15 or ei>len(w)-5:return None
        si=max(range(max(0,ei-60),ei),key=lambda i:w[i]["h"])
        hi,lo=w[si]["h"],w[ei]["l"]; rng=hi-lo
        pb=max(x["h"] for x in w[ei+1:])
        if pb<lo+.25*rng or not any(x["c"]>hi-.66*rng for x in w[ei+1:]):return None
        return make("LONG",lo,hi,pb,a)

def make(side,lo,hi,pb,a):
    if side=="SHORT":
        levels={k:hi-(hi-lo)*k for k in [0,.66,.70,.786,.83,1]}
        e1,e2=levels[.786],levels[.83]; sl=hi-min(hi*.01,5); tp=lo
    else:
        levels={k:lo+(hi-lo)*k for k in [0,.66,.70,.786,.83,1]}
        e1,e2=levels[.786],levels[.83]; sl=lo+min(lo*.01,5); tp=hi
    return {"side":side,"entry1":e1,"entry2":e2,"sl":sl,"tp":tp,"score":75,"fib":levels}

def scan_once():
    for s in SYMBOLS:
        for tf in TFS:
            try:
                c=candles(s,tf); sig=detect(c)
                if not sig: continue
                p=c[-1]["c"]; tol=max(atr(c)*.2,p*.001)
                if min(abs(p-sig["entry1"]),abs(p-sig["entry2"]))>tol: continue
                key=f"{s}:{tf}:{sig['side']}:{round(sig['entry1'],4)}"
                if key in last_sent: continue
                last_sent.add(key)
                tg(f"🚨 CHOCH SIGNAL\n\n{s} | {tf}\nSIDE: {sig['side']}\nSCORE: {sig['score']}/100\nPRICE: {p}\nENTRY 1: {sig['entry1']:.6f}\nENTRY 2: {sig['entry2']:.6f}\nSL: {sig['sl']:.6f}\nTP: {sig['tp']:.6f}\n\nWave-based: trend → extreme → pullback → structure change")
            except Exception as e: print("SCAN ERROR",s,tf,repr(e),flush=True)

def scanner():
    while True:
        try: scan_once()
        except Exception as e: print("SCANNER ERROR",repr(e),flush=True)
        time.sleep(int(os.getenv("SCAN_SECONDS","60")))

@app.get("/")
def home(): return jsonify({"service":"SignaBot CHOCH Engine","status":"online"})
@app.get("/health")
def health(): return jsonify({"status":"ok","engine":"choch_wave_v1"})
@app.get("/telegram-test")
def telegram_test(): return jsonify({"ok":tg("SignaBot CHOCH engine Telegram test successful.").get("ok",False)})
@app.get("/scan-test")
def scan_test():
    s=request.args.get("symbol","BTCUSDT").upper(); tf=request.args.get("timeframe","15m")
    c=candles(s,tf); return jsonify({"symbol":s,"timeframe":tf,"last_price":c[-1]["c"],"signal":detect(c)})
@app.post("/webhook/<secret>")
def webhook(secret):
    if not SECRET or secret!=SECRET:return jsonify({"error":"unauthorized"}),401
    d=request.get_json(silent=True)
    if d is None:return jsonify({"error":"invalid_json"}),400
    tg("TRADINGVIEW SIGNAL\n\n" + "\n".join(f"{k}: {v}" for k,v in d.items()))
    return jsonify({"status":"received","telegram":"sent"})

if os.getenv("ENABLE_SCANNER","false").lower()=="true":
    threading.Thread(target=scanner,daemon=True).start()
