# Deployment Guide

Production setup for a single Linux VPS running the FastAPI app (which
mounts both the Telegram and Stripe webhooks) behind nginx, with Postgres
and Redis alongside it. Adjust paths/domains for your own host.

## 1. Server prerequisites

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv postgresql redis-server nginx

sudo -u postgres psql << EOF
CREATE DATABASE ai_bugalter;
CREATE USER bugalter_user WITH PASSWORD 'CHANGE_ME';
ALTER ROLE bugalter_user SET client_encoding TO 'utf8';
ALTER ROLE bugalter_user SET default_transaction_isolation TO 'read committed';
GRANT ALL PRIVILEGES ON DATABASE ai_bugalter TO bugalter_user;
EOF
```

## 2. Deploy the app

```bash
mkdir -p /home/ai-bugalter && cd /home/ai-bugalter
git clone https://github.com/tjasurbek05-gif/AI-Bugalter.git .

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
chmod 600 .env
# Fill in: TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME, OPENAI_API_KEY,
#          STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / STRIPE_PRICE_*,
#          DATABASE_URL, REDIS_URL, WEBHOOK_URL, WEBHOOK_SECRET (random string),
#          APP_ENV=production

psql -U bugalter_user -d ai_bugalter -h localhost -f schema.sql
```

## 3. Stripe setup

1. Dashboard → Products: create 5 recurring prices matching the tiers in
   `app/handlers/payment.py::TIER_DISPLAY` (1 week / 1 month / 3 months /
   6 months / 1 year). Copy each Price ID into `.env` as
   `STRIPE_PRICE_1_WEEK`, `STRIPE_PRICE_1_MONTH`, etc.
2. Dashboard → Developers → Webhooks: add endpoint
   `https://<your-domain>/webhook/stripe`, subscribed to
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`. Copy the signing secret into
   `STRIPE_WEBHOOK_SECRET`.

## 4. Run as a service (systemd)

`/etc/systemd/system/ai-bugalter.service`:

```ini
[Unit]
Description=AI Bugalter FastAPI app
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
WorkingDirectory=/home/ai-bugalter
EnvironmentFile=/home/ai-bugalter/.env
ExecStart=/home/ai-bugalter/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-bugalter
sudo journalctl -u ai-bugalter -f
```

Prefer PM2? `pm2 start "venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000" --name ai-bugalter && pm2 save && pm2 startup`.

The app sets the Telegram webhook itself on startup (see `main.py`
`lifespan`) when `APP_ENV=production` and `WEBHOOK_URL` is set — no manual
`setWebhook` call needed.

## 5. nginx + TLS

```nginx
# /etc/nginx/sites-available/ai-bugalter
server {
    listen 80;
    server_name your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/ai-bugalter /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
sudo certbot --nginx -d your-domain.example   # TLS via Let's Encrypt
```

## 6. Verify

```bash
curl https://your-domain.example/health
# {"status":"ok","db":true}
```

Send `/start` to the bot on Telegram — you should get the welcome message.

## 7. Backups

```bash
# Daily pg_dump via cron
0 3 * * * pg_dump -U bugalter_user ai_bugalter | gzip > /var/backups/ai_bugalter_$(date +\%F).sql.gz
```

Keep at least 7 days of rotation; ship off-box (S3/Backblaze) for anything
you can't afford to lose.

## 8. Monitoring

- `GET /health` — wire into an uptime checker (UptimeRobot, etc.).
- Set `SENTRY_DSN` in `.env` to get error tracking for free (guarded init
  in `app/utils/logger.py` — a no-op if unset).
- Logs rotate under `logs/ai_bugalter.log` (5MB × 5 backups).
