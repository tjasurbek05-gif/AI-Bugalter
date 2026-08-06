# API Reference

AI Bugalter's primary interface is the Telegram bot itself (see "Bot Commands"
below). The FastAPI app (`main.py`) only exposes the minimal HTTP surface
needed to receive webhooks and report health — there is no public CRUD API.

## HTTP Endpoints

### `GET /health`

Liveness/readiness probe. Checks DB connectivity.

```
200 {"status": "ok", "db": true}
503 {"status": "degraded", "db": false}
```

### `POST /webhook/telegram/{webhook_secret}`

Telegram sends bot updates here. `{webhook_secret}` must match
`WEBHOOK_SECRET` from `.env` — this is set as the path Telegram is
configured to call via `bot.set_webhook()` at app startup, so requests to
any other path 404 before reaching this handler.

- Rate limited: 100 requests/minute per source IP (`slowapi`).
- Body: a Telegram `Update` object (see [Telegram Bot API docs](https://core.telegram.org/bots/api#update)).
- Response: `{"ok": true}`.

### `POST /webhook/stripe`

Stripe sends subscription lifecycle events here (configure this URL in the
Stripe Dashboard → Developers → Webhooks, subscribed to at least
`checkout.session.completed`, `customer.subscription.updated`,
`customer.subscription.deleted`).

- Rate limited: 60 requests/minute per source IP.
- Requires a valid `Stripe-Signature` header (verified against
  `STRIPE_WEBHOOK_SECRET`); invalid/missing signatures get `400`.
- Response: `{"ok": true}`.

## Bot Commands

| Command | Tier | Description |
|---|---|---|
| `/start` | free | Onboarding + registers the user |
| `/help` | free | Command reference |
| *(voice message)* | free (capped) | Transcribe → parse → confirm → save an expense |
| `/add <amount> <description>` | free (capped) | Typed fallback for logging an expense (skips Whisper) |
| `/expenses` | free | This month's spending, grouped by category |
| `/report` | paid | This month's spending + AI insights + month-over-month trend |
| `/loan <lend\|owe> <amount> <person> [<N> <day\|week\|month\|year>]` | paid | Create a loan, with optional due date |
| `/loans` | paid | List active loans; inline buttons to mark as paid |
| `/categories` | free | List default + your custom categories |
| `/addcategory <name> [emoji]` | free | Add a custom category |
| `/language` | free | Switch bot language (ru/uz/en) |
| `/subscribe` | free | Show plans and get a Stripe Checkout link |

"free (capped)" = allowed on the free tier up to `FREE_TIER_MONTHLY_LIMIT`
(default 5) expenses/month; "paid" = requires any active subscription tier
(enforced by `app.utils.decorators.check_subscription`).

## Internal Service Layer

For contributors extending the bot, the reusable building blocks live in
`app/services/`:

- `db.py` — all DB reads/writes (`get_or_create_user`, `create_expense`,
  `create_loan`, aggregation helpers, etc.). Every function takes an
  `AsyncSession` explicitly, so it's trivial to unit test against SQLite.
- `whisper.py` — `transcribe_voice(audio_bytes) -> str`, raises
  `TranscriptionError` on failure.
- `gpt.py` — `parse_expense(text) -> ParsedExpense`, raises `ParsingError`;
  `generate_monthly_insights(category_totals, language) -> list[str]`.
- `cache.py` — Redis-backed transcription cache + generic JSON get/set.
- `stripe.py` — `create_checkout_session(...)`, `construct_webhook_event(...)`.
