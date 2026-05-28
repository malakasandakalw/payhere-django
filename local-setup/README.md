# Local Development Setup

This guide is for developers who want to run the project locally using a local PostgreSQL database.

---

## Prerequisites

- Python 3.11+
- PostgreSQL installed and running locally
- Redis installed and running locally (or use [Upstash](https://upstash.com) free tier)
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

> **Note on REDIS_URL:** If using local Redis, use `redis://` (single s). If using Upstash, use `rediss://` (double s) with your Upstash credentials.

---

## 4. Run migrations

This creates all database tables and automatically seeds all 6 subscription plans (Free, Pro Monthly, Pro Annual, Enterprise Monthly, Enterprise Annual, Test Daily) — no separate command needed for plans.

```bash
python manage.py migrate
```

After this completes, verify the plans were seeded by calling `GET /api/plans/` or checking the `payments_plan` table in your database. If plans are missing for any reason, load them manually:

```bash
python manage.py loaddata local-setup/fixtures/plans.json
```

---

## 5. Troubleshooting: payments tables not created

If after running `migrate` the `payments_*` tables are missing from your database, it means Django has stale migration records from a previous setup. Fix it by clearing those records and re-running the payments migrations:

```bash
# Step 1 — remove stale payments migration records
python manage.py dbshell -- -c "DELETE FROM django_migrations WHERE app = 'payments';"

# Step 2 — apply all payments migrations fresh
python manage.py migrate payments
```

This will properly create all tables and seed the plans.

---

## 6. Create a superuser (for Django admin)

```bash
python manage.py createsuperuser
```

Visit `http://localhost:8000/admin/` to manage users, plans, subscriptions, and transactions.

---

## 7. User data — pick your case

### Case A: Your database already has users (skip fixture loading)

Just run migrate — tables and plans are ready, your existing users are untouched.

```bash
python manage.py migrate
```

Use `GET /api/users/` to find the user IDs to pass in API calls.

---

### Case B: Fresh database with no users (load test users)

If your database has no users yet, load the sample fixture:

```bash
python manage.py loaddata local-setup/fixtures/users.json
```

All three test users have the same password: **`testpass123`**

| ID | Username | Email             |
|----|----------|-------------------|
| 1  | alice    | alice@example.com |
| 2  | bob      | bob@example.com   |
| 3  | carol    | carol@example.com |

> These users have no login/auth in the API — `user_id` is passed directly in requests. The password is only needed if you want to log in to the Django admin panel.

---

## 8. Run the app

You need three terminals running at the same time.

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

The API is now available at `http://localhost:8000/api/`.

---

## 9. Set up ngrok (for PayHere notify callback)

PayHere needs a public URL to POST payment results. Start ngrok and update your `.env`:

```bash
ngrok http 8000
```

Copy the `https://` URL and set it in `.env`:

```
PAYHERE_NOTIFY_URL=https://abc123.ngrok-free.app/api/payments/notify/
```

Then restart the Django server. The ngrok URL changes every session — update `.env` each time.

---

## Quick test

Once everything is running, verify the API is working:

```bash
# List users
curl http://localhost:8000/api/users/

# List plans
curl http://localhost:8000/api/plans/

# Get subscription for user 1
curl http://localhost:8000/api/subscriptions/me/?user_id=1
```
