# 📉 PriceWatch — Flipkart Price Tracker

> A **Multi-Agent AI System** that automatically tracks Flipkart product prices, detects price drops, and sends email alerts — built with Python, Streamlit, and SQLite.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.56-red?style=flat-square&logo=streamlit)
![Playwright](https://img.shields.io/badge/Playwright-1.44-green?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-built--in-lightgrey?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## 🎯 What It Does

Paste any Flipkart product URL → PriceWatch checks the price every 24 hours automatically → sends you an email when price drops below your target.

**Live Demo:** [pricewatchflipkart.onrender.com](https://pricewatchflipkart.onrender.com)

---

## 🧠 Multi-Agent Architecture

The system uses **3 independent agents** that work together in a pipeline:

```
User adds product URL
        ↓
  Orchestrator (runs every 24 hours)
        ↓
┌───────────────────────────────────────┐
│                                       │
▼               ▼                       ▼
Look Agent   Monitor Agent          Store Agent
(scrapes     (compares prices,      (saves to
 Flipkart)    sends email alert)     SQLite DB)
```

| Agent | Role | Technology |
|-------|------|-----------|
| **Look Agent** | Opens Flipkart in real browser, extracts current price | Playwright + BeautifulSoup |
| **Monitor Agent** | Compares new vs old price, decides if alert needed | Python + smtplib |
| **Store Agent** | Saves price history, reads data for charts | SQLite |
| **Orchestrator** | Coordinates all agents, runs on schedule | APScheduler |

---

## ✨ Features

- 🔍 **Real browser scraping** — Playwright handles Flipkart's anti-bot protection
- 📊 **Price history chart** — visualise price trends over 30 days
- 📉 **Drop detection** — alerts on 5%+ price drop OR target price reached
- 📧 **Email alerts** — automatic Gmail notifications
- ⏰ **24-hour automation** — checks all products daily without any manual action
- 🔄 **Deduplication** — never saves the same price twice
- 🗃️ **SQLite storage** — zero setup, single file database
- 🧩 **Works on any product** — mobiles, electronics, FMCG, fashion, appliances

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| UI | Streamlit | Free hosting, fast to build |
| Scraping | Playwright | Only way to bypass Flipkart 403 blocks |
| HTML Parsing | BeautifulSoup + lxml | Fast, reliable |
| Database | SQLite | Zero setup, built into Python |
| Scheduling | APScheduler | Runs 24-hour checks in background |
| Email | smtplib (Gmail) | Free, built into Python |
| Hosting | Render (free tier) | 750 hrs/month free |

---

## 🚀 Quick Start (Local)

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/PriceWatchFlipkart.git
cd PriceWatchFlipkart
```

### 2. Create virtual environment
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure environment
```bash
cp .env.example .env
```

Edit `.env` with your details:
```env
DB_PATH=PriceWatchFlipkart.db

# Email alerts (optional)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your@gmail.com
SMTP_PASS=your_gmail_app_password
```

> **How to get Gmail App Password:**
> 1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
> 2. Create an App Password for "Mail"
> 3. Copy the 16-character password to `.env`

### 5. Run
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## 📦 Project Structure

```
PriceWatchFlipkart/
├── app.py              ← Streamlit UI (entry point)
├── orchestrator.py     ← Coordinates all 3 agents
├── look_agent.py       ← Scrapes Flipkart price (Playwright)
├── monitor_agent.py    ← Detects drops, sends email alerts
├── store_agent.py      ← SQLite read/write operations
├── requirements.txt    ← Python dependencies
├── .env.example        ← Environment variables template
├── .gitignore          ← Ignores .env, database, venv
└── README.md           ← This file
```

---

## 🔄 How It Works — Step by Step

```
1. User pastes Flipkart URL → clicks "Start Tracking"

2. Orchestrator calls Look Agent:
   → Playwright opens real Chrome browser
   → Visits flipkart.com homepage (gets cookies)
   → Navigates to product page
   → Extracts price using CSS selector div.v1zwn29 / div.v1zwn20
   → Returns {name, price, url}

3. Orchestrator calls Store Agent:
   → Saves product to SQLite (products table)
   → Saves first price reading (price_history table)

4. Dashboard shows product card with current price + chart

5. Every 24 hours — APScheduler triggers Orchestrator:
   → Look Agent fetches fresh price
   → Monitor Agent compares with previous price
   → If price dropped 5%+ OR target reached → sends email
   → Store Agent saves new price reading
   → Chart updates automatically
```

---

## 🌐 Deploy Free on Render

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit — PriceWatch"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/PriceWatchFlipkart.git
git push -u origin main
```

### Step 2 — Create Render account
Sign up free at [render.com](https://render.com) — no credit card needed.

### Step 3 — New Web Service
1. Click **New** → **Web Service**
2. Connect GitHub → select `PriceWatchFlipkart`
3. Fill settings:

| Setting | Value |
|---------|-------|
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt && playwright install chromium && playwright install-deps` |
| Start Command | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |
| Instance Type | **Free** |

### Step 4 — Environment Variables
In Render Dashboard → **Environment** → Add:

```
DB_PATH        = /tmp/PriceWatchFlipkart.db
SMTP_HOST      = smtp.gmail.com
SMTP_USER      = your@gmail.com
SMTP_PASS      = your_app_password
```

### Step 5 — Deploy
Click **Create Web Service** → wait 3-4 minutes → your app is live!

> **Note on free tier:** Render free tier has ephemeral storage —
> database resets on restart. For persistent storage, use
> [Supabase](https://supabase.com) free PostgreSQL (500MB, no expiry).

---

## 📊 CSS Selector Map (Flipkart April 2026)

Tested across 5 product types:

| Class | Meaning | Products |
|-------|---------|---------|
| `div.v1zwn29` | Current selling price | Mobiles, Electronics |
| `div.v1zwn20` | MRP / Universal price | All product types |
| `div.v1zwn22` | Total with delivery | (ignored) |
| `div.v1zwn24` | Recommended products | (ignored) |

> If Flipkart changes their CSS classes, open `debug_flipkart.html`
> (auto-saved on failure), inspect the price element, and update
> the selectors in `look_agent.py`.

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 👨‍💻 Built By

**Abhishek** — AI/ML Engineer  
[GitHub](https://github.com/YOUR_USERNAME) · [LinkedIn](https://linkedin.com/in/YOUR_PROFILE) · [Upwork](https://upwork.com/freelancers/YOUR_PROFILE)

> *Built as a portfolio project demonstrating multi-agent AI systems,
> web scraping, and automated data pipelines.*
