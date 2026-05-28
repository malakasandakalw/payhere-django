# Local Development Setup

Guide for running this project locally with a local PostgreSQL database.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone and install](#1-clone-and-install)
3. [Create a local PostgreSQL database](#2-create-a-local-postgresql-database)
4. [Set up your .env file](#3-set-up-your-env-file)
5. [Run migrations](#4-run-migrations)
6. [Troubleshooting: payments tables not created](#5-troubleshooting-payments-tables-not-created)
7. [Run the app](#6-run-the-app)
8. [Set up ngrok](#7-set-up-ngrok)
9. [API Reference](#api-reference)

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

Three terminals are required. Each runs a separate process that the app depends on.

---

**Terminal 1 — Django API server**

The main backend. Handles all HTTP requests from the frontend and processes PayHere notify callbacks.

```bash
source venv/bin/activate
python manage.py runserver
```

API available at `http://localhost:8000/api/`.

---

**Terminal 2 — Celery Worker**

Executes background tasks. This is the process that actually *runs* jobs when they are triggered — sending emails, calling the PayHere API to cancel or retry subscriptions, moving subscriptions to expired status.

Without this running, background tasks will queue up but never execute.

```bash
source venv/bin/activate
celery -A config worker -l info
```

---

**Terminal 3 — Celery Beat**

The scheduler. Acts like a cron job — it reads the schedule defined in `config/settings.py` and fires the following tasks automatically every day:

| Time     | Task                                                          |
| -------- | ------------------------------------------------------------- |
| Midnight | Expire cancelled subscriptions; activate pending plan changes |
| 9:00 AM  | Send renewal reminder emails; alert users with failed payments |
| 10:00 AM | Retry failed payment charges (dunning logic)                  |

Without this running, none of the scheduled jobs will ever trigger. The worker would sit idle waiting for tasks that never arrive.

```bash
source venv/bin/activate
celery -A config beat -l info
```

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

## API Reference

There is no login system. Every API call identifies the user by passing `user_id` as a query parameter or in the request body. All responses are JSON.

---

### GET /api/users/

Returns a list of all active users in the database.

**Use:** Find user IDs to use in other API calls during development.

**Request**
```
GET /api/users/
```

**Response**
```json
[
  { "id": 1, "username": "alice", "first_name": "Alice", "last_name": "Fernando", "email": "alice@example.com" },
  { "id": 2, "username": "bob",   "first_name": "Bob",   "last_name": "Perera",   "email": "bob@example.com" }
]
```

**Internal process**
1. Queries `auth_user` for all active users
2. Returns serialized list — no business logic involved

---

### GET /api/plans/

Returns all active subscription plans. The frontend calls this to build the pricing page.

**Request**
```
GET /api/plans/
```

**Response**
```json
[
  {
    "id": "uuid",
    "name": "Pro Monthly",
    "tier": "pro",
    "tier_rank": 1,
    "billing_cycle": "monthly",
    "amount": "2500.00",
    "currency": "LKR",
    "payhere_recurrence": "1 Month",
    "payhere_duration": "Forever",
    "features": { "max_users": 10, "storage_gb": 50, "api_calls": 10000 },
    "is_active": true
  }
]
```

**Internal process**
1. Queries `payments_plan` where `is_active = true`
2. Orders by `tier_rank` then `billing_cycle`
3. Returns serialized list

**Billing cycle values:** `daily` | `monthly` | `annual`

---

### GET /api/subscriptions/me/

Returns the current subscription for a user. If the user has never subscribed before, a Free plan subscription is automatically created and returned.

**Request**
```
GET /api/subscriptions/me/?user_id=1
```

**Response**
```json
{
  "id": "uuid",
  "plan": { "name": "Pro Monthly", "tier": "pro", "amount": "2500.00", ... },
  "pending_plan": null,
  "status": "active",
  "started_at": "2026-01-01T00:00:00Z",
  "current_period_start": "2026-01-01T00:00:00Z",
  "current_period_end": "2026-02-01T00:00:00Z",
  "cancelled_at": null,
  "cancel_at_period_end": false,
  "grace_period_end": null,
  "retry_count": 0
}
```

**Internal process**
1. Looks up the user by `user_id`
2. Tries to find an existing subscription for that user
3. If none exists, creates a new subscription with the Free plan and `status = pending`
4. Returns the subscription with full plan details nested inside

**Subscription status values:**

| Status | Meaning |
| --- | --- |
| `pending` | No successful payment yet |
| `active` | Paid and within a valid billing period |
| `failed` | Recurring charge failed — within grace period, retrying |
| `cancelled` | User cancelled — still active until `current_period_end` |
| `expired` | Period ended after cancellation or all payment retries failed |

---

### POST /api/payments/initiate/

Starts a payment. Returns all the fields the frontend needs to submit a form to PayHere's hosted checkout page.

**Request**
```json
{ "user_id": 1, "plan_id": "uuid-of-chosen-plan" }
```

**Response**
```json
{
  "merchant_id": "123456",
  "return_url": "http://localhost:4200/payment/return",
  "cancel_url": "http://localhost:4200/payment/cancel",
  "notify_url": "https://your-ngrok-url/api/payments/notify/",
  "order_id": "ORD-1-1748000000",
  "items": "Pro Monthly",
  "currency": "LKR",
  "amount": "2500.00",
  "first_name": "Alice",
  "last_name": "Fernando",
  "email": "alice@example.com",
  "phone": "0771234567",
  "address": "No. 1, Test Street",
  "city": "Colombo",
  "country": "Sri Lanka",
  "hash": "ABCD1234ABCD1234ABCD1234ABCD1234",
  "recurrence": "1 Month",
  "duration": "Forever"
}
```

**Internal process**
1. Validates `user_id` and `plan_id` are provided
2. Confirms the plan exists and is not the Free plan (can't pay for Free)
3. Checks no other payment is already pending for this user
4. Generates a unique `order_id` in format `ORD-{user_id}-{timestamp}`
5. Creates a `PaymentOrder` record with `status = pending`
6. Generates an MD5 hash by combining `merchant_id + order_id + amount + currency + MD5(merchant_secret)` — PayHere uses this to verify the request wasn't tampered with
7. Returns all fields — the frontend takes these and submits them as a form POST directly to PayHere

**Error responses:**

| Situation | Status | Message |
| --- | --- | --- |
| Missing fields | 400 | `user_id and plan_id are required` |
| User not found | 404 | `User not found` |
| Plan not found or inactive | 404 | `Plan not found` |
| Free plan selected | 400 | `Cannot initiate payment for the free plan` |
| Payment already in progress | 400 | `A payment is already in progress for this user` |

---

### POST /api/payments/notify/

**This endpoint is called by PayHere only — never by the frontend.**

PayHere posts the result of every transaction here: initial payments, recurring charges, chargebacks, and cancellations. This is where subscriptions get activated or failed.

This endpoint always returns HTTP 200, even on errors. Any other status code causes PayHere to retry the notification indefinitely.

**PayHere sends (form POST, not JSON):**

| Field | Description |
| --- | --- |
| `merchant_id` | Your PayHere merchant ID |
| `order_id` | The order ID from initiate (for first payment) |
| `payment_id` | Unique PayHere transaction ID |
| `subscription_id` | PayHere subscription ID (sent on recurring charges) |
| `payhere_amount` | Charged amount |
| `payhere_currency` | Currency |
| `status_code` | Result of the transaction (see table below) |
| `md5sig` | Signature to verify the notification is genuine |
| `customer_token` | Token for future charges via PayHere API |
| `item_rec_status` | Recurring subscription status (Active, Cancelled, etc.) |
| `item_rec_date_next` | Next scheduled charge date |

**Status codes:**

| Code | Meaning | Action taken |
| --- | --- | --- |
| `2` | Payment successful | Subscription activated or renewed |
| `-1` | Cancelled by user | PaymentOrder marked as cancelled |
| `-2` | Payment failed | Subscription set to failed, grace period starts (4 days) |
| `-3` | Chargeback (bank reversal) | Same as failed — grace period starts |

**Internal process**
1. Parses and coerces all incoming fields to correct Python types
2. Checks if this `payment_id` was already processed — if yes, returns immediately (idempotency guard)
3. Verifies the MD5 signature using `merchant_id + order_id + amount + currency + status_code + MD5(merchant_secret)` — confirms the notification genuinely came from PayHere
4. Resolves context (user, plan, subscription):
   - First tries to find a `PaymentOrder` matching the `order_id` (first-time payment)
   - If not found, looks up the subscription by `subscription_id` (recurring charge — no order exists for these)
5. Creates a `PaymentTransaction` record storing everything including the raw payload
6. Based on the status code and signature result:
   - **Status 2 (success):** Activates the subscription — sets status to `active`, calculates new `current_period_end` based on the plan's billing cycle (daily/monthly/annual), saves the `payhere_subscription_id` and `customer_token`
   - **Status -2 or -3 (failed/chargeback):** Sets subscription to `failed`, sets `grace_period_end` to 4 days from now, sends a failure email to the user
   - **Status -1 (cancelled):** Marks the PaymentOrder as cancelled

---

### GET /api/payments/return/

PayHere redirects the user's browser here after a payment attempt completes. This URL does not contain any payment result data — it is just a landing page signal for the frontend.

**Request**
```
GET /api/payments/return/
```

**Response**
```json
{ "message": "Payment flow complete. Check subscription status." }
```

**Internal process**
1. Returns a simple message — no database operations
2. The frontend should poll `GET /api/subscriptions/me/` after landing here to get the actual subscription status, since PayHere's notify callback may arrive a few seconds after the browser redirect

---

### GET /api/payments/cancel-return/

PayHere redirects the user's browser here when they leave the checkout page without completing payment.

**Request**
```
GET /api/payments/cancel-return/?order_id=ORD-1-1748000000
```

**Response**
```json
{ "message": "Payment cancelled by user." }
```

**Internal process**
1. Reads the `order_id` from query params (PayHere appends this automatically)
2. Finds the matching `PaymentOrder` with `status = pending`
3. Updates its status to `cancelled`
4. Returns confirmation message

---

### GET /api/payments/history/

Returns all payment transactions for a user, newest first.

**Request**
```
GET /api/payments/history/?user_id=1
```

**Response**
```json
[
  {
    "id": "uuid",
    "order_id": "ORD-1-1748000000",
    "payment_id": "320027183837",
    "amount": "2500.00",
    "currency": "LKR",
    "status_code": 2,
    "status_message": "Successfully completed the payment.",
    "payment_method": "VISA",
    "card_holder_name": "Alice Fernando",
    "card_no": "************1234",
    "installment_number": 1,
    "item_rec_status": "Active",
    "item_rec_date_next": "2026-02-01",
    "md5sig_verified": true,
    "created_at": "2026-01-01T10:00:00Z"
  }
]
```

**Internal process**
1. Queries `payments_paymenttransaction` filtered by user, ordered by `created_at` descending
2. Returns all transactions — every charge, retry, and failed attempt is recorded here

---

### POST /api/subscriptions/cancel/

Cancels the user's active subscription. The user keeps full access until the end of the current billing period. PayHere is instructed to stop future automatic charges immediately.

**Request**
```json
{ "user_id": 1 }
```

**Response**
```json
{
  "id": "uuid",
  "plan": { "name": "Pro Monthly", ... },
  "status": "active",
  "cancel_at_period_end": true,
  "cancelled_at": "2026-01-15T08:00:00Z",
  "current_period_end": "2026-02-01T00:00:00Z",
  ...
}
```

**Internal process**
1. Validates the subscription is currently `active`
2. Checks it is not already scheduled for cancellation
3. Confirms a `payhere_subscription_id` exists (needed to call PayHere API)
4. Calls the PayHere Merchant API (`POST /merchant/v1/subscription/cancel`) using an OAuth token fetched from PayHere and cached in Redis — this stops PayHere from charging the card again
5. Sets `cancel_at_period_end = true` and records `cancelled_at`
6. Returns the updated subscription — status stays `active` until period ends

A nightly Celery job checks for subscriptions where `cancel_at_period_end = true` and `current_period_end` has passed, then moves them to `expired` and downgrades the plan to Free.

**Error responses:**

| Situation | Status | Message |
| --- | --- | --- |
| Subscription not active | 400 | `Subscription is not active` |
| Already scheduled for cancellation | 400 | `Subscription is already scheduled for cancellation` |
| No PayHere subscription ID | 400 | `No PayHere subscription ID found` |
| PayHere API error | 502 | `PayHere API error: ...` |

---

### POST /api/subscriptions/change-plan/

Schedules a plan change to take effect at the end of the current billing period. No payment is taken immediately.

**Request**
```json
{ "user_id": 1, "new_plan_id": "uuid-of-new-plan" }
```

**Response**
```json
{
  "direction": "upgrade",
  "message": "Plan change to Enterprise Monthly scheduled. Takes effect at end of current period.",
  "subscription": {
    "plan": { "name": "Pro Monthly", ... },
    "pending_plan": { "name": "Enterprise Monthly", ... },
    ...
  }
}
```

**Internal process**
1. Validates the new plan exists, is active, and is not the Free plan
2. Confirms the user is not already on the requested plan
3. Determines direction — `upgrade` if the new plan has a higher `tier_rank`, or same rank but switching from monthly to annual; otherwise `downgrade`
4. Saves the new plan as `pending_plan` on the subscription — current plan is unchanged
5. Returns the direction and a message the frontend can show the user

A nightly Celery job checks for subscriptions with a `pending_plan` whose period has ended. When triggered it cancels the old PayHere subscription, clears the period dates, sets status to `pending`, and emails the user to complete payment for the new plan.

**Error responses:**

| Situation | Status | Message |
| --- | --- | --- |
| Free plan requested | 400 | `Use the cancel endpoint to move to the free plan` |
| Already on this plan | 400 | `User is already on this plan` |
