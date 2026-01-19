# Math Lead Sniper - Setup Guide

This tool monitors Reddit and Google Alerts for people asking for math tutoring help, uses AI to filter out junk, and sends high-quality leads to Discord.

## Getting Your API Keys

### 1. Google Gemini API Key (FREE)

1. Go to: https://aistudio.google.com
2. Sign in with your Google account
3. If it asks you to accept terms, click Accept
4. Look for "Get API Key" button (usually top right or in sidebar)
5. Click "Create API Key"
6. Copy the key - it looks like: `AIzaSy...` (about 40 characters)
7. Save it somewhere safe

**Note:** Free tier gives you 15 requests per minute, which is plenty for this.

### 2. Discord Webhook URL (FREE)

1. Open Discord (app or browser)
2. Go to your server
3. Find the channel where you want lead notifications
4. Click the gear icon next to the channel name (Edit Channel)
5. Click "Integrations" in the left sidebar
6. Click "Create Webhook" (or "View Webhooks" then "New Webhook")
7. Give it a name like "Math Leads"
8. Click "Copy Webhook URL"
9. Save it - it looks like: `https://discord.com/api/webhooks/123456789/abcdefg...`

### 3. Google Alerts RSS (OPTIONAL)

If you want to also monitor Google Alerts:

1. Go to: https://google.com/alerts
2. Create an alert for something like: `"need math tutor" OR "struggling with calculus"`
3. Click the pencil icon to edit the alert
4. Change "Deliver to" from "Email" to "RSS feed"
5. Click "Create Alert"
6. Right-click "RSS" next to your alert and copy the link
7. That's your RSS URL

You can add multiple RSS URLs separated by commas.

## Installation

### Step 1: Clone or Download

Make sure you have the project files:
- `lead_sniper.py` - Main script
- `requirements.txt` - Python dependencies
- `.env.example` - Environment template

### Step 2: Set Up Environment

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your API keys:
   ```bash
   nano .env
   # or use any text editor
   ```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Or if you use pip3:
```bash
pip3 install -r requirements.txt
```

### Step 4: Run the Script

```bash
python lead_sniper.py
```

Or:
```bash
python3 lead_sniper.py
```

## What You'll See

The script will run continuously and print status messages like:

```
==================================================
Math Lead Sniper - Starting up...
==================================================

Monitoring 5 subreddits: HomeworkHelp, Calculus, learnmath, MathHelp, Precalculus

Press Ctrl+C to stop.

Checking r/HomeworkHelp...
Checking r/Calculus...
  Found potential lead in r/Calculus: Help with integration by parts...
  Checking with AI...
  AI says YES - sending to Discord!
  Lead sent to Discord!
Checking r/learnmath...
```

Press `Ctrl+C` to stop the script.

## Subreddits Monitored

By default, the script monitors:
- r/HomeworkHelp
- r/Calculus
- r/learnmath
- r/MathHelp
- r/Precalculus

You can edit `lead_sniper.py` to add or remove subreddits from the `SUBREDDITS` list.

## Trigger Keywords

Posts must contain at least one of these keywords to be considered:
- urgent, exam, tutor, fail, due, stuck, help, tomorrow, tonight, asap
- struggling, desperate, need help, don't understand, confused
- failing, test, quiz, midterm, final, assignment, homework
- please help, anyone help, can someone, i need

## How It Works

1. **Fetch Posts**: Gets new posts from Reddit using public JSON endpoints (no API key needed)
2. **Keyword Filter**: Only processes posts containing trigger keywords
3. **AI Filter**: Uses Google Gemini to determine if the post is from a real student seeking help
4. **Discord Notification**: Sends qualified leads to your Discord channel

The script also:
- Tracks seen posts to avoid duplicates
- Has a 1-hour cooldown per URL
- Handles rate limiting with automatic retry
- Checks Reddit every 2 minutes
- Checks Google Alerts every 5 minutes

## Troubleshooting

### "ERROR: DISCORD_WEBHOOK_URL not set"
Make sure your `.env` file exists and has the `DISCORD_WEBHOOK_URL` set correctly.

### "Rate limited, waiting..."
This is normal. Reddit and Discord have rate limits. The script will automatically wait and retry.

### No leads showing up
- Make sure your Discord webhook URL is correct
- Check that the subreddits have active posts
- The script only sends posts that pass both the keyword filter AND the AI filter

### Python errors on startup
Make sure you installed the dependencies:
```bash
pip install -r requirements.txt
```

## Running in Background

### On Linux/Mac (using screen)
```bash
screen -S leadsniper
python lead_sniper.py
# Press Ctrl+A then D to detach
# Use 'screen -r leadsniper' to reattach
```

### On Linux/Mac (using nohup)
```bash
nohup python lead_sniper.py > leads.log 2>&1 &
```

### Using systemd (Linux)
Create `/etc/systemd/system/leadsniper.service`:
```ini
[Unit]
Description=Math Lead Sniper
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 lead_sniper.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable leadsniper
sudo systemctl start leadsniper
```
