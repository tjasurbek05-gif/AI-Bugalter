# AI Bugalter 🧮💰

**AI Bugalter** — Your personal AI accountant on Telegram.

A voice-first Telegram bot for tracking expenses, loans, and financial insights with AI-powered categorization and monthly analytics. Send voice messages, get instant categorization, auto-track loans, and receive AI-generated financial insights every month.

---

## 🚧 Implementation Status

This repo currently implements the **Phase 1–4 roadmap** below end-to-end as working code:

| Area | Status |
|------|--------|
| Voice → Whisper → GPT-4 Mini parsing → confirm → save | ✅ Implemented (`app/handlers/expense.py`) |
| Free tier limit (5 txns/month) + `/add` typed fallback | ✅ Implemented |
| Loan creation, listing, mark-as-paid, due reminders | ✅ Implemented (`app/handlers/loan.py`) |
| Monthly report with AI insights + trends | ✅ Implemented (`app/handlers/report.py`) |
| Custom categories, language selection, onboarding | ✅ Implemented (`app/handlers/settings.py`) |
| Stripe checkout + subscription webhooks | ✅ Implemented (`app/handlers/payment.py`) |
| FastAPI app (Telegram + Stripe webhooks, health check, rate limiting) | ✅ Implemented (`main.py`) |
| Unit + DB-integration test suite | ✅ Implemented (`tests/`) |
| VPS provisioning, nginx, PM2, live Stripe products, Sentry project | ⬜ Infrastructure — follow `docs/DEPLOYMENT.md` |
| Post-launch polish (multi-currency, budget alerts, bill splitting, CSV/PDF export, mobile app) | ⬜ Not started — see Roadmap below |

See `docs/API.md` for the HTTP surface and `docs/DEPLOYMENT.md` for a step-by-step production deploy.

---

## 📋 Project Overview

**Problem**: People are busy. Manual expense tracking takes 30+ seconds per transaction. Loan tracking is scattered across messages/notes.

**Solution**: Send a voice message → Bot transcribes → AI categorizes → Auto-saves with instant confirmation → Monthly AI-generated financial insights.

**Business Model**: Freemium SaaS with subscription tiers (1 week, 1 month, 3 months, 6 months, 1 year).

**Target Market**: Uzbekistan/Russian-speaking users (emerging market = price-sensitive + Telegram adoption high).

**Brand**: AI Bugalter (Bugalter = Accountant in Russian/Uzbek) — positioning as your personal AI accountant.

**Profitability**: 79-92% margins at scale with <$100/month API costs for 500+ users.

---

## ✨ Core Features

### Phase 1 (MVP - Week 1-3)
- ✅ Voice message transcription (Whisper API)
- ✅ Expense intent parsing with AI (GPT-4 Mini)
- ✅ Expense categorization (auto + custom)
- ✅ Save to PostgreSQL
- ✅ Confirmation flow (before saving)
- ✅ View monthly expenses (text summary)
- ✅ Free tier (5 transactions/month)

### Phase 2 (Loans - Week 4-5)
- ✅ Loan creation ("I owe Khasan 50k for 1 month")
- ✅ Loan status tracking (pending, paid, overdue)
- ✅ Loan reminders (3 days before due date)
- ✅ Settle loans (mark as paid)
- ✅ View all active loans

### Phase 3 (Analytics - Week 6-7)
- ✅ Monthly expense breakdown by category
- ✅ AI-generated insights ("You spent 40% on food, consider meal prep")
- ✅ Category trends (month-over-month)
- ✅ Dashboard (text-based, Telegram-friendly)

### Phase 4+ (Polish & Scale)
- ✅ Custom category creation
- ⬜ Recurring expense templates ("Weekly gym = 50k")
- ⬜ Multi-currency support
- ⬜ Budget alerts ("You've hit 80% of food budget")
- ⬜ Bill splitting (split expense with group)
- ⬜ Export to CSV/PDF
- ⬜ Dark mode tracking (multi-user households)

---

## 🏗️ Tech Stack

```
Frontend:
├─ Telegram Bot (@username)
└─ aiogram 3.x (Python async bot framework)

Backend:
├─ FastAPI (main API)
├─ PostgreSQL (primary DB, via SQLAlchemy 2.0 async + asyncpg)
├─ Redis (caching + rate limiting + FSM storage)
└─ Contabo VPS (5.189.155.192, vmi3305627)

Infrastructure:
├─ PM2 (process management)
├─ nginx (reverse proxy)
├─ systemd (service management)
└─ DuckDNS (domain: resumeapi.duckdns.org reference)

AI/LLM:
├─ OpenAI Whisper API (speech → text)
├─ GPT-4 Mini (intent parsing + categorization)
└─ GPT-4 (monthly insights generation)

Payment:
└─ Stripe API (subscription management)

Monitoring:
├─ Sentry (error tracking, optional via SENTRY_DSN)
└─ Rotating file logging
```

> **Note on the DB driver**: the original spec listed `psycopg2-binary` (sync). Since both aiogram 3 and FastAPI are fully async, this implementation uses **SQLAlchemy 2.0's async engine with `asyncpg`** instead — a sync driver would block the event loop under load. The SQL schema (`schema.sql`) is unchanged and works with either driver.

---

## 💸 API Costs Breakdown

### Per User Per Month (10 transactions/month average)

| Service | Rate | Volume | Cost |
|---------|------|--------|------|
| Whisper API | $0.012/min | 10 min | $0.12 |
| GPT-4 Mini | $0.00015/1K tokens | 1,500 tokens | $0.23 |
| Monthly Summary (GPT-4) | $0.003/1K tokens | 2,000 tokens | $0.01 |
| Infrastructure overhead | — | — | $0.04 |
| **Total** | — | — | **$0.40/user/month** |

### Cost per Subscription Tier

| Tier | Duration | API Cost | Fixed Cost* | Total Cost |
|------|----------|----------|-------------|-----------|
| 1 Week | 7 days | $0.10 | $0.50 | $0.60 |
| 1 Month | 30 days | $0.40 | $0.50 | $0.90 |
| 3 Months | 90 days | $1.20 | $1.50 | $2.70 |
| 6 Months | 180 days | $2.40 | $3.00 | $5.40 |
| 1 Year | 365 days | $4.80 | $6.00 | $10.80 |

*Fixed cost: prorated VPS ($80/mo) + Stripe fees (2.9% + $0.30) + support buffer

---

## 💰 Pricing Tiers & Profit Margins

### Subscription Plans

```
FREE TIER (Forever Free)
├─ 5 transactions/month
├─ Basic categorization
├─ No analytics
└─ Goal: Convert to paid

1-WEEK TIER: $1.49
├─ 100 transactions/week
├─ Full features
├─ Goal: Low-friction trial
└─ Margin: 63%

1-MONTH TIER: $4.99 ⭐ PRIMARY
├─ Unlimited transactions
├─ AI categorization
├─ Monthly insights
├─ Loan tracking
└─ Margin: 86%

3-MONTH TIER: $12.99 (discount: $4.33/mo)
├─ All features
├─ Priority support
└─ Margin: 84%

6-MONTH TIER: $22.99 (discount: $3.83/mo)
├─ All features
├─ 15% cheaper than monthly
└─ Margin: 82%

1-YEAR TIER: $39.99 (discount: $3.33/mo)
├─ All features
├─ 33% cheaper than monthly
├─ Annual upfront payment
└─ Margin: 79%
```

### Revenue Projections (100 Active Users)

```
Realistic split (weighted towards 1-month tier):
├─ 15 users × $1.49/week = $96/month
├─ 40 users × $4.99/month = $199.60/month
├─ 25 users × $12.99/qtr = $108.25/month
├─ 15 users × $22.99/semi = $57.45/month
└─ 5 users × $39.99/year = $16.66/month

TOTAL REVENUE: $477.96/month
API COSTS: $40/month
FIXED COSTS: $80/month
PROFIT: $357.96/month (75% margin)
```

### Revenue Projections (500 Active Users)

```
TOTAL REVENUE: $2,389.80/month
API COSTS: $200/month
FIXED COSTS: $80/month
PROFIT: $2,109.80/month (88% margin) ✅
```

---

## 📊 Database Schema

### Users Table
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username VARCHAR(255),
  first_name VARCHAR(255),
  language_code VARCHAR(10) DEFAULT 'en',
  subscription_tier VARCHAR(50) DEFAULT 'free',
  subscription_expires_at TIMESTAMP,
  stripe_customer_id VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE
);
```

### Expenses Table
```sql
CREATE TABLE expenses (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount DECIMAL(12, 2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'UZS',
  category VARCHAR(50) NOT NULL, -- 'food', 'transport', 'utilities', 'custom_*'
  description TEXT,
  voice_message_id VARCHAR(255), -- Telegram message ID
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_expenses_user_date ON expenses (user_id, created_at);
```

### Loans Table
```sql
CREATE TABLE loans (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type VARCHAR(20) NOT NULL, -- 'lend' (they owe you) or 'owe' (you owe them)
  person_name VARCHAR(255) NOT NULL,
  amount DECIMAL(12, 2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'UZS',
  due_date DATE,
  status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'paid', 'overdue'
  description TEXT,
  reminder_sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_loans_user_status ON loans (user_id, status);
```

### Categories Table (Custom)
```sql
CREATE TABLE categories (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(50) NOT NULL,
  emoji VARCHAR(10),
  color VARCHAR(10),
  UNIQUE(user_id, name)
);
```

### Subscriptions Table (Stripe Integration)
```sql
CREATE TABLE subscriptions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  stripe_subscription_id VARCHAR(255) UNIQUE,
  stripe_price_id VARCHAR(255),
  tier VARCHAR(50) NOT NULL, -- '1_week', '1_month', '3_months', etc
  status VARCHAR(50) DEFAULT 'active', -- 'active', 'canceled', 'past_due'
  current_period_start DATE,
  current_period_end DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

See `schema.sql` for the full, runnable DDL (indexes included).

---

## 🤖 Bot Conversation Flows

### Flow 1: Send Voice Message (Create Expense)

```
User sends voice message
    ↓
Bot receives voice → downloads file
    ↓
Call Whisper API → transcribe to text
    ↓
Call GPT-4 Mini with prompt:
"Parse this expense: '{transcription}'
Return JSON: {amount: number, category: string, description: string}"
    ↓
Bot replies with CONFIRMATION:
"✅ Got it!
💵 100,000 UZS
🏪 Category: Food
📝 Lunch at Cheburek place

[✅ Confirm] [✏️ Edit] [🗑️ Cancel]"
    ↓
User taps [✅ Confirm]
    ↓
Save to DB → Show success animation
    ↓
"💾 Saved! You've spent 250k this month."
```

### Flow 2: Create Loan

```
User types: "/loan lend 50000 Khasan 1 month"
    ↓
Bot parses: type=lend, amount=50k, person=Khasan, due_date=today+30days
    ↓
Confirmation:
"📋 Confirm loan:
Khasan owes you: 50,000 UZS
Due: [date]

[✅ Create] [❌ Cancel]"
    ↓
User confirms
    ↓
Save to DB → Reminder sent automatically 3 days before due date
    ↓
"✅ Loan created! I'll remind you around [date]"
```

### Flow 3: View Monthly Report

```
User types: "/report"
    ↓
Fetch all expenses from this month
    ↓
Aggregate by category
    ↓
Call GPT-4 with prompt:
"User spent: food=500k, transport=200k, utilities=100k, other=50k
Generate 2-3 short, friendly insights in Russian"
    ↓
Bot sends:
"📊 Your Money This Month

🍔 Food: 500k (50%)
🚕 Transport: 200k (20%)
🏠 Utilities: 100k (10%)
📌 Other: 50k (5%)

💡 Insights:
• You spent 20% more on food than last month. Consider meal prep?
• Transport is steady at 200k/mo
• Save 5k next month for emergency fund"
```

### Flow 4: View Active Loans

```
User types: "/loans"
    ↓
Fetch all loans from DB
    ↓
Bot sends:
"📋 Your Loans

💰 You are owed:
├─ Khasan: 50,000 UZS (Due: Dec 15) ⏰
├─ Maria: 100,000 UZS (Due: Jan 5)

💳 You owe:
├─ Dad: 500,000 UZS (Due: Dec 20) ⚠️ OVERDUE
├─ Bank: 1,000,000 UZS (Due: Jan 30)

[✅ Mark as paid: Khasan (50,000 UZS)]
[✅ Mark as paid: Maria (100,000 UZS)]
..."
```

---

## 🔧 Installation & Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Redis
- OpenAI API key
- Stripe API key
- Telegram Bot Token

### Step 1: Clone & Install

```bash
git clone https://github.com/tjasurbek05-gif/AI-Bugalter.git
cd AI-Bugalter

python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
# for running the test suite too:
pip install -r requirements-dev.txt
```

### Step 2: Environment Variables

```bash
cp .env.example .env
# then fill in TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, STRIPE_* etc.
chmod 600 .env
```

### Step 3: Database Setup

```bash
psql -U postgres << EOF
CREATE DATABASE ai_bugalter;
CREATE USER bugalter_user WITH PASSWORD 'secure_password';
ALTER ROLE bugalter_user SET client_encoding TO 'utf8';
ALTER ROLE bugalter_user SET default_transaction_isolation TO 'read committed';
GRANT ALL PRIVILEGES ON DATABASE ai_bugalter TO bugalter_user;
EOF

psql -U bugalter_user -d ai_bugalter -f schema.sql
```

### Step 4: Run

```bash
# Option A: local dev bot via long polling (no public URL needed)
python bot.py

# Option B: production-style, FastAPI serving both the Telegram + Stripe webhooks
uvicorn main:app --host 0.0.0.0 --port 8000
```

See `docs/DEPLOYMENT.md` for PM2 + nginx + webhook production setup.

---

## 📁 Project Structure

```
ai-bugalter/
├── main.py                 # FastAPI app entry (webhooks, health check)
├── bot.py                  # Telegram bot handler (aiogram) + polling entrypoint
├── config.py                # Settings from .env
├── requirements.txt        # Dependencies
├── requirements-dev.txt    # + test dependencies
├── schema.sql               # Database schema
├── pytest.ini
├── .env.example             # Environment variable template
├── .gitignore
│
├── app/
│   ├── handlers/
│   │   ├── expense.py     # Expense voice → save logic
│   │   ├── loan.py        # Loan creation & tracking
│   │   ├── report.py      # Monthly report generation
│   │   ├── settings.py    # Onboarding, language, categories
│   │   └── payment.py     # Stripe subscription checkout + webhooks
│   ├── services/
│   │   ├── whisper.py     # Whisper API wrapper
│   │   ├── gpt.py         # GPT-4 wrapper (parsing, insights)
│   │   ├── db.py          # Database engine + query helpers
│   │   ├── stripe.py      # Stripe integration
│   │   └── cache.py       # Redis caching
│   ├── models/
│   │   ├── user.py
│   │   ├── expense.py
│   │   ├── loan.py
│   │   ├── category.py
│   │   └── subscription.py
│   └── utils/
│       ├── logger.py
│       ├── decorators.py  # @check_subscription, @log_errors
│       ├── validators.py
│       └── formatting.py
│
├── tests/
│   ├── conftest.py
│   ├── test_expense.py
│   ├── test_loan.py
│   └── test_report.py
│
└── docs/
    ├── API.md            # Full API spec
    └── DEPLOYMENT.md     # Deploy guide
```

---

## 🔐 Security & Best Practices

- **Rate limiting** on both webhook endpoints via `slowapi` (100/min Telegram, 60/min Stripe).
- **`@check_subscription(min_tier="paid")`** gates loans/reports behind an active subscription; expenses are gated by a free-tier monthly counter instead.
- **`@log_errors`** wraps every handler so unhandled exceptions are logged and degrade gracefully instead of crashing the bot.
- **Stripe webhook signature verification** (`stripe.Webhook.construct_event`) rejects unsigned/forged requests.
- **Telegram webhook secret** embedded in the URL path (`/webhook/telegram/<secret>`), so the path itself acts as a bearer credential.
- **TLS**: terminate at nginx/Caddy in front of the app (see `docs/DEPLOYMENT.md`).

### Data Privacy

- Users can request data export/deletion (their `users` row cascades to expenses/loans/categories/subscriptions on delete).
- Secrets live only in `.env` (gitignored, `chmod 600`).
- No Telegram voice files are retained — only the transcribed text is briefly cached (24h) for retry purposes.

---

## 📈 Development Roadmap

### Week 1-3: MVP (Phase 1) — ✅ done in this repo
- [x] Setup FastAPI + PostgreSQL + aiogram
- [x] Whisper API integration (voice → text)
- [x] GPT-4 Mini integration (text → parsed expense)
- [x] Confirmation flow UI
- [x] `/expenses` command (list this month)
- [x] Free tier (5 transactions/month limit)
- [x] Error handling & logging

### Week 4-5: Loans (Phase 2) — ✅ done in this repo
- [x] Loan creation flow
- [x] Loan status tracking
- [x] Due date reminder (3 days before)
- [x] `/loans` command (view all)
- [x] Mark as paid flow

### Week 6-7: Analytics (Phase 3) — ✅ done in this repo
- [x] Category aggregation
- [x] GPT-4 insights generation
- [x] `/report` command (monthly summary)
- [x] Spending trends

### Week 8+: Monetization — ✅ done in this repo
- [x] Stripe integration (checkout sessions)
- [x] Subscription tier logic (`@check_subscription`)
- [x] Webhook handling (subscription lifecycle)
- [x] Payment confirmation flow

### Post-Launch: Polish & Scale — not started
- [ ] Recurring expenses
- [ ] Budget alerts
- [ ] Bill splitting
- [ ] Export (CSV/PDF)
- [ ] Multi-language UI strings (Russian, Uzbek, English) — `language_code` is stored today, translated strings are next
- [ ] Mobile app (optional)

---

## 🚀 Launch Checklist

### Pre-Launch
- [x] Test coverage on critical paths (parsing, validation, tier gating, aggregation)
- [ ] Manual testing with 20 beta users
- [ ] Sentry monitoring setup (`SENTRY_DSN` wired in `app/utils/logger.py`, needs a real project)
- [ ] Stripe sandbox testing
- [ ] Database backups automated (daily)
- [ ] Rate limiting tuned for real traffic
- [ ] Privacy policy & ToS written

### Launch Day
- [ ] Deploy to production
- [ ] Set Telegram webhook
- [ ] Announce in 5-10 Telegram groups
- [ ] Monitor errors in real-time
- [ ] Be ready to hotfix

### Week 1
- [ ] Monitor churn rate (target: <10%)
- [ ] Check API costs (should be <$5)
- [ ] Iterate on UX pain points
- [ ] Respond to user feedback

### Month 1
- [ ] Measure conversion (free → paid)
- [ ] Identify top use cases
- [ ] Plan Phase 2 features
- [ ] Start customer interviews

---

## 💡 Key Success Metrics

```
Activation: % of users who send first voice message (target: >60%)
Retention: % of users active after 7 days (target: >40%)
Conversion: % of free users → paid (target: >5%)
Churn: % of paid users canceling (target: <15%/month)
LTV: Lifetime value per user (target: >$50)
CAC: Customer acquisition cost (target: <$5)
```

---

## 🆘 Troubleshooting

### Whisper API Latency Issues
- Transcriptions are cached in Redis for 24h, keyed by Telegram's `file_unique_id`.
- Bot shows a "🎙️ Transcribing..." status message immediately.
- Fallback: `/add <amount> <description>` for manual text entry.

### GPT-4 Mini Hallucinations
- The bot always requires user confirmation (✅/✏️/🗑️) before saving.
- Malformed/incomplete GPT responses raise `ParsingError` and fall back to a manual-entry prompt instead of saving garbage.
- `/edit` flow lets the user correct amount/category/description before confirming.

### Database Connection Issues
- `pool_pre_ping=True` on the SQLAlchemy engine recycles dead connections automatically.
- Health check endpoint: `GET /health` (checks DB connectivity).

### Stripe Webhook Failures
- Webhook signature is verified before any processing; invalid signatures get HTTP 400.
- Unrecognized event types are logged and ignored rather than erroring.

---

## 📞 Support & Contribution

- **Issues**: Report bugs in Telegram group
- **Feature Requests**: Voting system (users vote on features)
- **Development**: Open to community contributions

---

## 📄 License

MIT License - Open source with commercial support available.

---

## 🎯 TL;DR — AI Bugalter

**What we're building**: Voice-first expense + loan tracker bot on Telegram. Your personal AI accountant.

**Why it works**: 10x faster data entry than manual. 92% profit margins. Uzbek market gap.

**Timeline**: MVP in 3 weeks. Monetize in 8 weeks.

**Revenue Model**: Free tier (5 txns/mo) + $4.99/month ($3.33/year).

**At 500 users**: $2,389/month revenue, $2,109/month profit (88% margin).

**Stack**: aiogram 3, FastAPI, PostgreSQL, Whisper + GPT-4, Stripe.

**Bugalter** = Accountant in Russian/Uzbek. Perfect positioning.

---

**Ready to build?** Phase 1–4 are implemented — see `docs/DEPLOYMENT.md` to ship it. 🚀
