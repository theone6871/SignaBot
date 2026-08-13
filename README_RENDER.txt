RENDER DEPLOY
1. Upload this folder to a GitHub repository.
2. Render -> New -> Web Service -> select repository.
3. Build Command: pip install -r requirements.txt
4. Start Command: gunicorn -w 2 -b 0.0.0.0:$PORT webhook.server:app
5. Environment variables:
   TELEGRAM_TOKEN
   TELEGRAM_CHAT_ID
   WEBHOOK_SECRET
6. After deploy:
   https://YOUR-RENDER-DOMAIN/health
   Expected: {"status":"ok"}
7. TradingView webhook:
   https://YOUR-RENDER-DOMAIN/webhook/YOUR_WEBHOOK_SECRET
