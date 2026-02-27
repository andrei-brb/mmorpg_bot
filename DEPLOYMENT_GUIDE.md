# 🚀 Deployment Guide - Keep Bot Running 24/7

## Option 1: Railway (Recommended - Easiest & Free Tier)

### Steps:

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub (free)

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your repository (or create one first)

3. **Set Environment Variables**
   In Railway dashboard, go to your project → Variables tab, add:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   DATABASE_URL=your_postgresql_connection_string
   ```
   Optional: `LOG_LEVEL=WARNING` to reduce log volume and avoid Railway rate limits.
   
   **For Database:**
   - Railway provides PostgreSQL for free
   - Go to "New" → "Database" → "PostgreSQL"
   - Copy the DATABASE_URL from the database service
   - Add it to your bot's environment variables

4. **Deploy**
   - Railway will automatically detect Python and deploy
   - Your bot will start running!

**Cost:** Free tier includes $5 credit/month (usually enough for a Discord bot)

---

## Option 2: Render (Alternative Free Option)

### Steps:

1. **Create Render Account**
   - Go to https://render.com
   - Sign up (free)

2. **Create Web Service**
   - Click "New" → "Web Service"
   - Connect your GitHub repo
   - Settings:
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python main.py`
     - **Environment:** Python 3

3. **Add Environment Variables**
   - Go to "Environment" tab
   - Add:
     - `DISCORD_TOKEN`
     - `DATABASE_URL`

4. **Add PostgreSQL Database**
   - Click "New" → "PostgreSQL"
   - Copy the connection string to `DATABASE_URL`

**Cost:** Free tier (may sleep after inactivity, but wakes on activity)

---

## Option 3: VPS (More Control, ~$5-10/month)

### Recommended Providers:
- **DigitalOcean** ($6/month droplet)
- **Linode** ($5/month)
- **Vultr** ($6/month)
- **Hetzner** (€4/month - cheapest)

### Steps:

1. **Create VPS**
   - Choose Ubuntu 22.04
   - Minimum: 1GB RAM, 1 CPU

2. **SSH into Server**
   ```bash
   ssh root@your_server_ip
   ```

3. **Install Dependencies**
   ```bash
   # Update system
   apt update && apt upgrade -y
   
   # Install Python & pip
   apt install python3 python3-pip python3-venv postgresql -y
   
   # Install PostgreSQL client
   apt install postgresql-client -y
   ```

4. **Clone Your Bot**
   ```bash
   # Install git
   apt install git -y
   
   # Clone your repo (or upload files)
   git clone your_repo_url
   cd mmorpg_bot
   ```

5. **Setup Bot**
   ```bash
   # Create virtual environment
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Create .env file
   nano .env
   # Add your DISCORD_TOKEN and DATABASE_URL
   ```

6. **Setup PostgreSQL**
   ```bash
   # Create database
   sudo -u postgres psql
   CREATE DATABASE mmorpg;
   CREATE USER mmorpg_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE mmorpg TO mmorpg_user;
   \q
   ```

7. **Run Bot as Service (keeps running)**
   ```bash
   # Create systemd service
   sudo nano /etc/systemd/system/mmorpg-bot.service
   ```
   
   Add this content:
   ```ini
   [Unit]
   Description=MMORPG Discord Bot
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/mmorpg_bot
   Environment="PATH=/root/mmorpg_bot/.venv/bin"
   ExecStart=/root/mmorpg_bot/.venv/bin/python main.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```
   
   ```bash
   # Enable and start
   sudo systemctl enable mmorpg-bot
   sudo systemctl start mmorpg-bot
   
   # Check status
   sudo systemctl status mmorpg-bot
   ```

---

## Option 4: Replit (Free, but may have limitations)

1. Go to https://replit.com
2. Create new Python repl
3. Upload your bot files
4. Set environment variables in Secrets tab
5. Use "Always On" feature (requires Replit Hacker plan or free tier with limitations)

---

## 🎯 Quick Comparison

| Option | Cost | Difficulty | Reliability |
|--------|------|-----------|-------------|
| **Railway** | Free/$5 | ⭐ Easy | ⭐⭐⭐⭐⭐ |
| **Render** | Free | ⭐ Easy | ⭐⭐⭐⭐ |
| **VPS** | $5-10/mo | ⭐⭐⭐ Medium | ⭐⭐⭐⭐⭐ |
| **Replit** | Free/Paid | ⭐⭐ Easy | ⭐⭐⭐ |

---

## 📝 Before Deploying

1. **Push to GitHub** (if using Railway/Render):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/mmorpg_bot.git
   git push -u origin main
   ```

2. **Get Your Database URL**
   - If using Railway/Render: They provide it automatically
   - If using external PostgreSQL: Format is:
     ```
     postgresql://username:password@host:port/database
     ```

3. **Get Discord Bot Token**
   - From Discord Developer Portal
   - Keep it secret!

---

## ✅ Recommended: Railway

**Why Railway?**
- ✅ Easiest setup
- ✅ Free tier ($5 credit/month)
- ✅ Automatic deployments
- ✅ Built-in PostgreSQL
- ✅ Great documentation

**Quick Start:**
1. Sign up at railway.app
2. New Project → Deploy from GitHub
3. Add environment variables
4. Done! Bot runs 24/7

---

Need help? Check the logs in your hosting platform's dashboard!
