# Local Development Setup

Guide for running this project locally with a local PostgreSQL database.

---

## Prerequisites

- Python 3.11+
- PostgreSQL running locally
- Redis running locally (or use [Upstash](https://upstash.com) free tier)
- [ngrok](https://ngrok.com) for PayHere notify URL

---

## 1. Clone and install

```bash
git clone https://github.com/malakasandakalw/payhere-django.git
cd payhere-django

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 2. Create a local PostgreSQL database

```bash
psql -U postgres
```

```sql
CREATE DATABASE payhere_django;
\q
```

---

## 3. Set up your .env file

Create a `.env` file in the project root:

```
SECRET_KEY=any-long-random-string-here

DATABASE_URL=postgresql://postgres:your-password@localhost:5432/payhere_django

REDIS_URL=redis://localhost:6379

PAYHERE_MERCHANT_ID=your-sandbox-merchant-id
PAYHERE_MERCHANT_SECRET=your-sandbox-merchant-secret
PAYHERE_APP_ID=your-sandbox-app-id
PAYHERE_APP_SECRET=your-sandbox-app-secret
PAYHERE_SANDBOX=true
PAYHERE_BASE_URL=https://sandbox.payhere.lk

PAYHERE_NOTIFY_URL=https://your-ngrok-url/api/payments/notify/
PAYHERE_RETURN_URL=http://localhost:4200/payment/return
PAYHERE_CANCEL_URL=http://localhost:4200/payment/cancel
```

> **Note on REDIS_URL:** Local Redis uses `redis://` (single s). Upstash uses `rediss://` (double s).

---

## 4. Run migrations

Creates all tables and seeds all 6 plans automatically.

```bash
python manage.py migrate
```

---

## 5. Troubleshooting: payments tables not created

If the `payments_*` tables are missing after migrate, clear stale migration records and re-run:

```bash
python manage.py dbshell -- -c "DELETE FROM django_migrations WHERE app = 'payments';"
python manage.py migrate payments
```

---

## 6. Run the app

Three terminals required.

**Terminal 1 — Django**
```bash
source venv/bin/activate
python manage.py runserver
```

**Terminal 2 — Celery Worker**
```bash
source venv/bin/activate
celery -A config worker -l info
```

**Terminal 3 — Celery Beat**
```bash
source venv/bin/activate
celery -A config beat -l info
```

API available at `http://localhost:8000/api/`.

---

## 7. Set up ngrok

PayHere requires a public URL for payment callbacks. Start ngrok and update `.env`:

```bash
ngrok http 8000
```

```
PAYHERE_NOTIFY_URL=https://abc123.ngrok-free.app/api/payments/notify/
```

Restart Django after updating. The ngrok URL changes every session.

---

## Quick test

```bash
# List plans
curl http://localhost:8000/api/plans/

# Get subscription for a user
curl http://localhost:8000/api/subscriptions/me/?user_id=1
```
