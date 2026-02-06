# Razorpay Integration Setup

## Overview
This document covers the complete Razorpay integration for Subhamasthu's Sankalp Seva payment processing.

## Configuration

### Environment Variables (Railway)
```
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

### Webhook URL
```
https://web-production-b998a.up.railway.app/webhooks/razorpay
```

---

## Razorpay Dashboard Setup

### Step 1: Create Webhook
1. Login to Razorpay Dashboard
2. Go to **Settings → Webhooks**
3. Click **+ Add New Webhook**
4. Configure:
   - **Webhook URL**: `https://web-production-b998a.up.railway.app/webhooks/razorpay`
   - **Secret**: Generate and copy (add to Railway as `RAZORPAY_WEBHOOK_SECRET`)
   - **Active Events**:
     - ✅ `payment_link.paid`
     - ✅ `payment.captured`
     - ✅ `payment_link.expired`
5. Click **Create Webhook**

### Step 2: Get API Keys
1. Go to **Settings → API Keys**
2. Copy Key ID → Add to Railway as `RAZORPAY_KEY_ID`
3. Copy Key Secret → Add to Railway as `RAZORPAY_KEY_SECRET`

---

## Payment Flow

```
User selects Tyagam ($21/$51/$108)
         │
         ▼
┌─────────────────────────────┐
│ SankalpService creates      │
│ Razorpay Payment Link       │
│ with sankalp_id in notes    │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Link sent via WhatsApp      │
│ User opens and pays         │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Razorpay sends webhook      │
│ payment_link.paid           │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ PaymentService:             │
│ - Verifies signature        │
│ - Creates Payment record    │
│ - Updates Sankalp status    │
│ - Creates SevaLedger entry  │
│ - Sends Telugu receipt      │
│ - User → COOLDOWN state     │
└─────────────────────────────┘
```

---

## Webhook Events Handled

| Event | Handler | Action |
|-------|---------|--------|
| `payment_link.paid` | `handle_payment_link_paid()` | Complete payment, send receipt |
| `payment.captured` | `handle_payment_captured()` | Backup handler |
| `payment_link.expired` | `handle_payment_link_expired()` | Mark EXPIRED, notify user |

---

## Pricing Tiers (USD)

| Tier | Amount | Families Fed |
|------|--------|--------------|
| సాముహిక | $21 | 10 |
| విశేష | $51 | 25 |
| ప్రత్యేక | $108 | 50 |

---

## Ledger Split
- **80%** → Annadanam Seva
- **20%** → Platform Fee

---

## Testing

### Test Payment Link Creation
```bash
curl -X POST https://web-production-b998a.up.railway.app/admin/test-payment \
  -H "X-Admin-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json"
```

### Simulate Webhook (Local)
```bash
curl -X POST http://localhost:8000/webhooks/razorpay \
  -H "Content-Type: application/json" \
  -d '{"event": "payment_link.paid", "payload": {...}}'
```

---

## Troubleshooting

### Webhook Not Receiving
1. Check Railway logs for errors
2. Verify webhook URL is correct
3. Check if webhook is active in Razorpay dashboard

### Signature Verification Failed
1. Ensure `RAZORPAY_WEBHOOK_SECRET` matches dashboard
2. Check for extra whitespace in env var

### Payment Not Reflecting
1. Check logs for `sankalp_id` in notes
2. Verify Sankalp record exists
3. Check idempotency (duplicate event_id)
