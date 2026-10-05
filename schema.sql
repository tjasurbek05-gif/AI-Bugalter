-- AI Bugalter database schema (PostgreSQL 13+)
-- Run with: psql -U bugalter_user -d ai_bugalter -f schema.sql

BEGIN;

-- ── Users ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username VARCHAR(255),
  first_name VARCHAR(255),
  language_code VARCHAR(10) DEFAULT 'en',
  subscription_tier VARCHAR(50) DEFAULT 'free', -- 'free', '1_week', '1_month', '3_months', '6_months', '1_year', 'premium_1_day', 'premium_1_week', 'premium_1_month'
  subscription_expires_at TIMESTAMP,
  stripe_customer_id VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE
);

-- ── Expenses ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS expenses (
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
CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses (user_id, created_at);

-- ── Loans ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loans (
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
CREATE INDEX IF NOT EXISTS idx_loans_user_status ON loans (user_id, status);

-- ── Categories (custom) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(50) NOT NULL,
  emoji VARCHAR(10),
  color VARCHAR(10),
  UNIQUE(user_id, name)
);

-- ── Subscriptions (Stripe) ───────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
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
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id);

-- ── Click transactions (click.uz premium payments) ──────
CREATE TABLE IF NOT EXISTS click_transactions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  merchant_trans_id VARCHAR(64) UNIQUE NOT NULL,
  click_trans_id VARCHAR(64),
  tier VARCHAR(50) NOT NULL, -- 'premium_1_day', 'premium_1_week', 'premium_1_month'
  amount DECIMAL(12, 2) NOT NULL,
  state INTEGER DEFAULT 0, -- 0 created, 1 waiting for complete, 2 paid, -1/-2 cancelled
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_click_transactions_user ON click_transactions (user_id);
CREATE INDEX IF NOT EXISTS idx_click_transactions_click_trans_id ON click_transactions (click_trans_id);

COMMIT;
