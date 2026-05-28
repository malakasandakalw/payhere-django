# PayHere Django Backend

Django REST API backend for PayHere subscription billing. Handles the full SaaS subscription lifecycle — plan selection, recurring payments via PayHere, cancellations, plan changes, dunning (failed payment retries), and automated email notifications.

Built for sandbox testing against the PayHere payment gateway (Sri Lanka).

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Tech Stack](#tech-stack)
3. [Subscription Plans](#subscription-plans)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Environment Variables](#environment-variables)
7. [Running the App](#running-the-app)
8. [API Reference](#api-reference)
9. [Frontend Integration Guide](#frontend-integration-guide)
10. [PayHere Payment Flow](#payhere-payment-flow)
11. [Subscription Lifecycle](#subscription-lifecycle)
12. [Background Jobs](#background-jobs)

---

## How It Works

This backend sits between your frontend and PayHere. The frontend never talks to PayHere directly — it asks this backend to initiate a payment, gets back the form fields it needs, then submits those fields to PayHere's hosted checkout page. After the user pays, PayHere calls this backend's notify endpoint to confirm the payment, and the backend activates the subscription.

There is no login system. For testing, every API call passes a `user_id` to identify the user (as a query parameter or request body field).

---

## Tech Stack

| Layer                  | Technology                           |
| ---------------------- | ------------------------------------ |
| Framework              | Django 6 + Django REST Framework     |
| Database               | PostgreSQL (Supabase)                |
| Cache / Message Broker | Redis (Upstash)                      |
| Background Jobs        | Celery + Celery Beat                 |
| Payment Gateway        | PayHere (Sri Lanka)                  |
| Email (dev)            | Console backend (prints to terminal) |

---

## Subscription Plans

Five plans are seeded into the database automatically via migrations.

| Plan               | Billing | Amount     |
| ------------------ | ------- | ---------- |
| Free               | —       | LKR 0      |
| Pro Monthly        | Monthly | LKR 2,500  |
| Pro Annual         | Annual  | LKR 25,000 |
| Enterprise Monthly | Monthly | LKR 8,000  |
| Enterprise Annual  | Annual  | LKR 80,000 |

Each plan has a `features` JSON field: `{ max_users, storage_gb, api_calls }`.

---

## Prerequisites

- Python 3.11+
- A PostgreSQL database (Supabase free tier works)
- A Redis instance (Upstash free tier works — use the `rediss://` URL)
- [ngrok](https://ngrok.com) for exposing your local server to PayHere
- A PayHere sandbox account at [sandbox.payhere.lk](https://sandbox.payhere.lk)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/malakasandakalw/payhere-django.git
cd payhere-django

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install django djangorestframework psycopg2-binary dj-database-url \
    python-dotenv requests python-dateutil django-redis celery \
    redis djangorestframework

# 4. Copy the environment file and fill in your values
cp .env.example .env
# Edit .env with your database URL, Redis URL, and PayHere credentials

# 5. Run migrations (creates all tables and seeds the 5 plans)
python manage.py migrate

# 6. Create a Django superuser (for admin panel access)
python manage.py createsuperuser

# 7. Create test users via the admin panel
#    Visit http://localhost:8000/admin and add users under Authentication → Users
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in every value.

| Variable                  | Where to find it                                    | Description                                          |
| ------------------------- | --------------------------------------------------- | ---------------------------------------------------- |
| `SECRET_KEY`              | Generate one                                        | Django secret key — any long random string           |
| `DATABASE_URL`            | Supabase → Project Settings → Database              | Full PostgreSQL connection string                    |
| `REDIS_URL`               | Upstash → Redis → Details                           | Must start with `rediss://` (double s) for TLS       |
| `PAYHERE_MERCHANT_ID`     | PayHere Dashboard → Settings → Domain & Credentials | Your sandbox merchant ID                             |
| `PAYHERE_MERCHANT_SECRET` | PayHere Dashboard → Settings → Domain & Credentials | Used to sign payment hashes                          |
| `PAYHERE_APP_ID`          | PayHere Dashboard → Settings → Apps                 | Used for Merchant API (cancel/retry)                 |
| `PAYHERE_APP_SECRET`      | PayHere Dashboard → Settings → Apps                 | OAuth secret for Merchant API                        |
| `PAYHERE_SANDBOX`         | —                                                   | Set to `true` for sandbox testing                    |
| `PAYHERE_BASE_URL`        | —                                                   | `https://sandbox.payhere.lk` for sandbox             |
| `PAYHERE_NOTIFY_URL`      | Your backend URL                                    | PayHere POSTs payment results here — must be public  |
| `PAYHERE_RETURN_URL`      | —                                                   | PayHere redirects user here after successful payment |
| `PAYHERE_CANCEL_URL`      | —                                                   | PayHere redirects user here if they abandon payment  |

**Important about `PAYHERE_NOTIFY_URL`:** PayHere needs to reach your backend from the internet. During development, use ngrok:

```bash
ngrok http 8000
# Copy the https URL, e.g. https://abc123.ngrok-free.app
# Set PAYHERE_NOTIFY_URL=https://abc123.ngrok-free.app/api/payments/notify/
```

The ngrok URL changes every session. Update `.env` and restart Django each time.

---

## Running the App

You need three terminals running at the same time.

**Terminal 1 — Django (the API server)**

```bash
source venv/bin/activate
python manage.py runserver
```

**Terminal 2 — Celery Worker (runs background jobs)**

```bash
source venv/bin/activate
celery -A payhere_vertext worker -l info
```

**Terminal 3 — Celery Beat (schedules the jobs)**

```bash
source venv/bin/activate
celery -A payhere_vertext beat -l info
```

The API is available at `http://localhost:8000/api/`.

---

## API Reference

All endpoints are prefixed with `/api/`. Responses are JSON.

---

### GET /api/users/

List all active users. Used in development to find user IDs for testing other endpoints.

**Request**

```
GET /api/users/
```

**Response**

```json
[
  {
    "id": 1,
    "username": "alice",
    "first_name": "Alice",
    "last_name": "Silva",
    "email": "alice@example.com"
  },
  {
    "id": 2,
    "username": "bob",
    "first_name": "Bob",
    "last_name": "Perera",
    "email": "bob@example.com"
  }
]
```

---

### GET /api/plans/

List all active subscription plans. Call this to build the pricing page. Plans are ordered by tier and billing cycle.

**Request**

```
GET /api/plans/
```

**Response**

```json
[
  {
    "id": "uuid",
    "name": "Free",
    "tier": "free",
    "tier_rank": 0,
    "billing_cycle": "",
    "amount": "0.00",
    "currency": "LKR",
    "payhere_recurrence": "",
    "payhere_duration": "",
    "features": { "max_users": 1, "storage_gb": 1, "api_calls": 100 },
    "is_active": true
  },
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

---

### GET /api/subscriptions/me/

Get the current subscription for a user. If the user has never subscribed, it automatically creates a Free plan subscription and returns it.

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
  "started_at": "2025-06-01T10:00:00Z",
  "current_period_start": "2025-06-01T10:00:00Z",
  "current_period_end": "2025-07-01T10:00:00Z",
  "cancelled_at": null,
  "cancel_at_period_end": false,
  "grace_period_end": null,
  "retry_count": 0
}
```

**Subscription statuses:**

| Status      | Meaning                                                                |
| ----------- | ---------------------------------------------------------------------- |
| `pending`   | Created but no successful payment yet                                  |
| `active`    | Paid and in a valid billing period                                     |
| `failed`    | Recurring payment failed — in grace period                             |
| `cancelled` | User cancelled — still active until `current_period_end`               |
| `expired`   | Period ended after cancellation, or moved to Free after failed payment |

---

### POST /api/payments/initiate/

Start a payment. Returns all the fields needed to submit to PayHere's checkout. Call this when the user clicks "Subscribe" or "Upgrade".

**Request**

```json
{
  "user_id": 1,
  "plan_id": "uuid-of-pro-monthly-plan"
}
```

**Response**

```json
{
  "merchant_id": "1234567",
  "return_url": "http://localhost:4200/payment/return",
  "cancel_url": "http://localhost:4200/payment/cancel",
  "notify_url": "https://abc123.ngrok-free.app/api/payments/notify/",
  "order_id": "ORD-1-1748000000",
  "items": "Pro Monthly",
  "currency": "LKR",
  "amount": "2500.00",
  "first_name": "Alice",
  "last_name": "Silva",
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

Take every field from this response and submit it as a form POST to PayHere. See the [Frontend Integration Guide](#frontend-integration-guide) for the exact code.

---

### POST /api/payments/notify/

**This endpoint is called by PayHere, not by your frontend.**

PayHere posts payment results here after every transaction (initial payment, recurring charge, chargeback, cancellation). This endpoint verifies the signature, records the transaction, and updates the subscription accordingly.

Always returns HTTP 200. Any other status code would cause PayHere to retry indefinitely.

**Status codes PayHere sends:**

| Code | Meaning                    | Action taken                         |
| ---- | -------------------------- | ------------------------------------ |
| `2`  | Payment successful         | Activates or renews the subscription |
| `-1` | Payment cancelled by user  | Marks the payment order as cancelled |
| `-2` | Payment failed             | Starts grace period + dunning        |
| `-3` | Chargeback (bank reversal) | Same as failed — starts grace period |

---

### GET /api/payments/return/

PayHere redirects the user's browser here after a payment attempt. This does not contain payment data — use it only to trigger a UI state change. Poll `/api/subscriptions/me/` to get the actual subscription status.

**Response**

```json
{ "message": "Payment flow complete. Check subscription status." }
```

---

### GET /api/payments/cancel-return/

PayHere redirects the user's browser here if they leave the checkout without paying.

**Query params:** `?order_id=ORD-1-1748000000` (sent by PayHere automatically)

**Response**

```json
{ "message": "Payment cancelled by user." }
```

---

### GET /api/payments/history/

List all payment transactions for a user, newest first.

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
    "card_holder_name": "Alice Silva",
    "card_no": "************1234",
    "installment_number": 1,
    "md5sig_verified": true,
    "created_at": "2025-06-01T10:00:00Z"
  }
]
```

---

### POST /api/subscriptions/cancel/

Cancel the user's active subscription. The subscription stays active until the end of the current billing period (`current_period_end`), then expires automatically. PayHere stops future charges immediately.

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
  "cancelled_at": "2025-06-15T08:00:00Z",
  "current_period_end": "2025-07-01T10:00:00Z",
  ...
}
```

When `cancel_at_period_end` is `true`, show the user a message like: "Your subscription will end on July 1, 2025."

---

### POST /api/subscriptions/change-plan/

Schedule a plan change to take effect at the end of the current billing period. No payment is taken immediately. At period end, the old PayHere subscription is cancelled and the user is emailed to complete payment for the new plan.

**Request**

```json
{ "user_id": 1, "new_plan_id": "uuid-of-enterprise-monthly-plan" }
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

`direction` is either `"upgrade"` or `"downgrade"`. Use it to show appropriate messaging in the UI.

---

## Frontend Integration Guide

### Step 1 — Load the pricing page

```typescript
// On your pricing page component init
this.http.get<Plan[]>("http://localhost:8000/api/plans/").subscribe((plans) => {
  this.plans = plans.filter((p) => p.tier !== "free"); // show paid plans only
});
```

### Step 2 — Load the user's current subscription

```typescript
const userId = 1; // replace with actual user ID from your auth system

this.http
  .get<Subscription>(
    `http://localhost:8000/api/subscriptions/me/?user_id=${userId}`,
  )
  .subscribe((subscription) => {
    this.subscription = subscription;
  });
```

### Step 3 — Initiate a payment (the most important step)

When the user clicks "Subscribe", call `/api/payments/initiate/`, then take the response fields and submit them to PayHere via a hidden HTML form. This is a full-page redirect — PayHere does not support iframe or popup checkout.

```typescript
subscribe(planId: string) {
  const body = { user_id: this.userId, plan_id: planId };

  this.http.post<any>('http://localhost:8000/api/payments/initiate/', body)
    .subscribe(data => {
      this.submitToPayHere(data);
    });
}

submitToPayHere(data: any) {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = 'https://sandbox.payhere.lk/pay/checkout'; // use https://www.payhere.lk/pay/checkout in production

  const fields = [
    'merchant_id', 'return_url', 'cancel_url', 'notify_url',
    'order_id', 'items', 'currency', 'amount',
    'first_name', 'last_name', 'email', 'phone',
    'address', 'city', 'country', 'hash',
    'recurrence', 'duration'
  ];

  fields.forEach(key => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = data[key];
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
}
```

### Step 4 — Handle the return from PayHere

PayHere redirects the user's browser to `PAYHERE_RETURN_URL` after payment. Create a route in your frontend for this (e.g. `/payment/return`). On that page, poll the subscription endpoint until the status becomes `active`.

```typescript
// payment-return.component.ts
ngOnInit() {
  this.pollSubscription();
}

pollSubscription() {
  const poll = setInterval(() => {
    this.http.get<Subscription>(`http://localhost:8000/api/subscriptions/me/?user_id=${this.userId}`)
      .subscribe(sub => {
        if (sub.status === 'active') {
          clearInterval(poll);
          this.router.navigate(['/dashboard']);
        }
      });
  }, 2000); // check every 2 seconds

  // Stop polling after 30 seconds regardless
  setTimeout(() => clearInterval(poll), 30000);
}
```

**Why poll?** PayHere calls the notify URL asynchronously. The user's browser may arrive at the return page a few seconds before PayHere has posted the payment confirmation.

### Step 5 — Cancel a subscription

```typescript
cancelSubscription() {
  this.http.post('http://localhost:8000/api/subscriptions/cancel/', { user_id: this.userId })
    .subscribe((sub: any) => {
      // sub.cancel_at_period_end === true
      // sub.current_period_end has the date access ends
      const endDate = new Date(sub.current_period_end).toLocaleDateString();
      alert(`Your subscription will end on ${endDate}.`);
    });
}
```

### Step 6 — Change plan

```typescript
changePlan(newPlanId: string) {
  const body = { user_id: this.userId, new_plan_id: newPlanId };
  this.http.post<any>('http://localhost:8000/api/subscriptions/change-plan/', body)
    .subscribe(result => {
      console.log(result.direction); // 'upgrade' or 'downgrade'
      console.log(result.message);   // human-readable explanation
    });
}
```

### Step 7 — Show payment history

```typescript
loadHistory() {
  this.http.get<any[]>(`http://localhost:8000/api/payments/history/?user_id=${this.userId}`)
    .subscribe(transactions => {
      this.transactions = transactions;
    });
}
```

---

## PayHere Payment Flow

This is the complete sequence from button click to activated subscription.

```
User clicks Subscribe
        │
        ▼
POST /api/payments/initiate/
(backend creates PaymentOrder, returns signed form fields)
        │
        ▼
Frontend submits hidden form to https://sandbox.payhere.lk/pay/checkout
(full-page redirect — user is now on PayHere's hosted page)
        │
        ▼
User enters card details and confirms payment
        │
        ├──────────────────────────────────────────────────────┐
        ▼                                                      ▼
PayHere POSTs to /api/payments/notify/            PayHere redirects browser to
(backend verifies signature, records              PAYHERE_RETURN_URL
transaction, activates subscription)              (frontend polls /subscriptions/me/)
```

**Important:** The notify callback and the browser redirect happen independently. Always rely on the notify callback for subscription activation — never trust the return URL alone.

---

## Subscription Lifecycle

```
[New User]
    │
    ▼
status: pending (Free plan)
    │
    │  User pays via PayHere → notify_url receives status 2
    ▼
status: active ──────────────────────────────┐
    │                                        │
    │  PayHere auto-renews monthly/annually  │
    │  (notify_url receives status 2 again)  │
    │◄───────────────────────────────────────┘
    │
    ├── User cancels → cancel_at_period_end = true
    │       │
    │       │  Period ends (midnight Celery job)
    │       ▼
    │   status: expired → plan downgraded to Free
    │
    ├── PayHere charge fails → status: failed
    │       │  grace_period_end set to now + 4 days
    │       │  Celery retries daily for 4 days
    │       │
    │       ├── Retry succeeds (notify_url receives status 2)
    │       │       ▼
    │       │   status: active (resumed)
    │       │
    │       └── All retries fail → status: expired → plan downgraded to Free
    │
    └── User requests plan change → pending_plan set
            │
            │  Period ends (midnight Celery job)
            │  Old PayHere subscription cancelled
            ▼
        status: pending (new plan)
        User must re-pay to activate new plan
```

---

## Background Jobs

Celery Beat runs these jobs automatically. You must have the Celery worker and beat processes running (Terminals 2 and 3).

| Job                              | Schedule       | What it does                                                                                                                                                             |
| -------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `expire_cancelled_subscriptions` | Daily midnight | Finds subscriptions where `cancel_at_period_end=True` and the period has ended. Moves them to `expired`, downgrades to Free plan, sends email.                           |
| `activate_pending_plan_changes`  | Daily 12:05 AM | Finds subscriptions with a `pending_plan` where the period has ended. Cancels the old PayHere subscription and emails the user to pay for the new plan.                  |
| `send_renewal_reminders`         | Daily 9:00 AM  | Sends a heads-up email to users whose subscription renews in exactly 3 days. No action needed from the user — PayHere auto-charges their saved card.                     |
| `alert_failed_subscriptions`     | Daily 9:05 AM  | Sends a warning email to all users currently in `failed` status.                                                                                                         |
| `process_dunning_retries`        | Daily 10:00 AM | For each failed subscription within the grace period, calls the PayHere retry API. If the grace period has expired, moves the user to Free plan and sends a final email. |

---

## Django Admin

Visit `http://localhost:8000/admin/` with your superuser credentials to:

- Create and manage test users
- View all subscriptions and their current status
- Browse payment orders and transaction history
- Inspect raw PayHere notify payloads (stored in `raw_payload`)
