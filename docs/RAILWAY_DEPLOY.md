# Deploy to Railway

## Prerequisites
- [Railway account](https://railway.app) (free tier available)
- [Railway CLI](https://docs.railway.app/develop/cli) installed (optional but recommended)

## Option A: Deploy via Railway Dashboard (Easiest)

### Step 1: Connect GitHub Repository

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select the `pranith-akula/subhamasthu` repository
6. Railway will auto-detect the Python project

### Step 2: Add Environment Variables

In Railway Dashboard:
1. Click on your service
2. Go to **Variables** tab
3. Add all variables from your `.env` file:

```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=rediss://...
OPENAI_API_KEY=sk-...
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
GUPSHUP_API_KEY=...
GUPSHUP_APP_NAME=...
GUPSHUP_SOURCE_NUMBER=...
ADMIN_API_KEY=...
SECRET_KEY=...
APP_ENV=production
DEBUG=false
```

### Step 3: Deploy

1. Railway will automatically deploy on push to main branch
2. Check deployment logs for any errors
3. Once deployed, get your URL from **Settings** → **Domains**

### Step 4: Generate Domain

1. Go to **Settings** → **Networking** → **Generate Domain**
2. You'll get a URL like: `subhamasthu-production.up.railway.app`

---

## Option B: Deploy via Railway CLI

### Step 1: Install Railway CLI

```powershell
# Windows (PowerShell)
iwr -useb https://cli.railway.app | pwsh -c -

# Or via npm
npm install -g @railway/cli
```

### Step 2: Login and Initialize

```bash
cd c:\Users\akula\Desktop\Subhamasthu
railway login
railway init
```

### Step 3: Link to Existing Project (if created via dashboard)

```bash
railway link
```

### Step 4: Deploy

```bash
railway up
```

### Step 5: View Logs

```bash
railway logs
```

---

## After Deployment

### Verify Health
```bash
curl https://your-app.railway.app/health
```

### Update Webhook URLs

1. **Gupshup**: Set webhook to `https://your-app.railway.app/webhooks/gupshup`
2. **Razorpay**: Set webhook to `https://your-app.railway.app/webhooks/razorpay`

### Your URLs

After deployment, update these in respective services:
- **Health Check**: `https://your-app.railway.app/health`
- **API Docs**: `https://your-app.railway.app/docs`
- **Gupshup Webhook**: `https://your-app.railway.app/webhooks/gupshup`
- **Razorpay Webhook**: `https://your-app.railway.app/webhooks/razorpay`

---

## Troubleshooting

### Build Fails
- Check `requirements.txt` has all dependencies
- Ensure Python version is 3.11+

### Database Connection Error
- Verify DATABASE_URL is correct
- Check SSL is enabled (use `postgresql+asyncpg://`)

### Application Crashes
- Check Railway logs: `railway logs`
- Verify all environment variables are set
