# Deploying Price Tracker to Render (Free)

## What you get
- Live public URL (e.g. https://price-tracker-abc.onrender.com)
- Runs 24/7 (free tier spins down after 15 min of inactivity)
- Automatic price checks every 24 hours
- Zero cost

## Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/price-tracker.git
git push -u origin main
```

## Step 2 — Create Render account
Go to https://render.com and sign up (free, no credit card).

## Step 3 — Create Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub account
3. Select your `price-tracker` repository
4. Fill in these settings:

| Setting | Value |
|---|---|
| Name | price-tracker |
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |
| Instance Type | Free |

## Step 4 — Set Environment Variables (optional)

In Render dashboard → Environment → Add these if you want email alerts:

```
SMTP_HOST = smtp.gmail.com
SMTP_USER = your@gmail.com
SMTP_PASS = your_gmail_app_password
DB_PATH   = /tmp/prices.db
```

**How to get Gmail App Password:**
1. Go to myaccount.google.com → Security
2. Enable 2-Step Verification
3. Go to App Passwords → Create one for "Mail"
4. Copy the 16-character password

## Step 5 — Deploy
Click **Create Web Service**. Render will build and deploy automatically.
Your app will be live at: https://price-tracker-xxx.onrender.com

## Important: Database on Free Tier

Render's free tier has an **ephemeral filesystem** — the database
resets every time the service restarts.

**For demo purposes:** This is fine. Data persists during a session.

**For production:** Use Supabase free tier (500MB PostgreSQL, no expiry):
1. Create account at supabase.com (free)
2. Create a new project → get the connection string
3. Set `DATABASE_URL` environment variable in Render
4. Update `store_agent.py` to use psycopg2 instead of sqlite3

## Local Development

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/price-tracker
cd price-tracker
pip install -r requirements.txt

# Run locally
streamlit run app.py

# Open http://localhost:8501
```

## File Structure

```
price-tracker/
├── app.py              ← Streamlit UI (entry point)
├── orchestrator.py     ← Coordinates all agents
├── look_agent.py       ← Scrapes Flipkart price
├── monitor_agent.py    ← Detects drops, sends alerts
├── store_agent.py      ← SQLite read/write
├── requirements.txt    ← Python dependencies
└── DEPLOY.md           ← This file
```
