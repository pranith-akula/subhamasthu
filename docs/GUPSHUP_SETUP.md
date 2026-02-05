# Gupshup WhatsApp Setup Guide

## Step 1: After Verification is Complete

Once your WhatsApp Business verification is approved:

1. Go to [Gupshup Console](https://www.gupshup.io/developer/home)
2. Select your app
3. Note down these values for your `.env`:
   - **API Key**: Found in "API Settings" or "Dashboard"
   - **App Name**: Your app's name in Gupshup
   - **Source Number**: Your verified WhatsApp Business number

## Step 2: Configure Webhook URL

In Gupshup Console:

1. Go to **Manage** → **Integrations** or **Webhook Settings**
2. Set **Callback/Webhook URL** to:
   ```
   https://your-railway-app.railway.app/webhooks/gupshup
   ```
3. Set **HTTP Method** to `POST`
4. Enable webhook for:
   - ✅ Incoming messages
   - ✅ Message status updates
   - ✅ Button replies

## Step 3: Update Your .env File

Add these values to your `.env`:

```env
# Gupshup WhatsApp
GUPSHUP_API_KEY=your-api-key-from-gupshup-console
GUPSHUP_APP_NAME=your-app-name
GUPSHUP_SOURCE_NUMBER=919876543210  # Your verified WhatsApp number
GUPSHUP_WEBHOOK_SECRET=your-webhook-secret  # Optional, for signature verification
```

## Step 4: Test the Integration

### 4.1 Send a Test Message

From Gupshup Console:
1. Go to **Test** → **Send Message**
2. Send a test message to yourself

### 4.2 Verify Webhook is Receiving

Check your Railway logs:
```bash
railway logs
```

You should see incoming webhook events.

### 4.3 Run the Onboarding Test

Once configured, run:
```bash
python scripts/test_onboarding.py
```

## Webhook Payload Format

Gupshup sends payloads in this format:

```json
{
  "app": "YourAppName",
  "timestamp": 1699900000000,
  "version": 2,
  "type": "message",
  "payload": {
    "id": "message-id",
    "source": "919876543210",
    "type": "text",
    "payload": {
      "text": "Hi"
    },
    "sender": {
      "phone": "919876543210",
      "name": "User Name"
    }
  }
}
```

## Button Reply Format

When a user clicks a button:

```json
{
  "type": "button_reply",
  "payload": {
    "title": "Button Text",
    "id": "BUTTON_PAYLOAD_ID"
  }
}
```

## Troubleshooting

### Webhook Not Receiving Messages
- Check webhook URL is correct
- Verify SSL certificate is valid (Railway provides this)
- Check Gupshup webhook logs

### Messages Not Sending
- Verify API key is correct
- Check if number is verified in Gupshup
- Look at Railway logs for errors

### Rate Limits
- Gupshup has rate limits (varies by plan)
- Implement retry logic for failed sends
