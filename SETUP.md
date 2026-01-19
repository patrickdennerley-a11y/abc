# Math Lead Sniper - Setup Guide

A Python script that monitors Reddit for math tutoring leads, filters them with Gemini AI, and sends notifications to Discord.

## Prerequisites

- Python 3.8+
- A Gemini API key (free)
- A Discord webhook URL

## Installation

### 1. Clone and navigate to the directory

```bash
cd /path/to/project
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
GEMINI_API_KEY=your_gemini_api_key_here
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## Getting API Keys

### Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key to your `.env` file

### Discord Webhook URL

1. Open Discord and go to your server
2. Right-click on the channel where you want notifications
3. Click "Edit Channel" → "Integrations" → "Webhooks"
4. Click "New Webhook"
5. Give it a name (e.g., "Math Lead Sniper")
6. Click "Copy Webhook URL"
7. Paste the URL in your `.env` file

## Usage

### Run the monitor

```bash
python lead_sniper.py
```

The script will:
1. Check all configured subreddits every 5 minutes
2. Filter posts for trigger keywords (urgent, exam, tutor, etc.)
3. Use Gemini AI to verify it's a real student needing help
4. Send Discord notifications for qualified leads

### Run once (for testing)

You can modify the script to run a single check by calling `run_check()` directly instead of `main()`.

## Configuration

Edit these variables in `lead_sniper.py` to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUBREDDITS` | HomeworkHelp, Calculus, etc. | Subreddits to monitor |
| `TRIGGER_KEYWORDS` | urgent, exam, tutor, etc. | Keywords to filter posts |
| `CHECK_INTERVAL_MINUTES` | 5 | Minutes between checks |
| `COOLDOWN_HOURS` | 1 | Hours before re-notifying same URL |

## Monitored Subreddits

- r/HomeworkHelp
- r/Calculus
- r/LearnMath
- r/MathHelp
- r/PreCalculus

## Trigger Keywords

Posts containing these words are analyzed:
- urgent
- exam
- tutor
- fail
- due
- stuck
- help
- tomorrow
- tonight
- asap
- struggling

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Reddit (Public JSON)                  │
│              old.reddit.com/r/*/new.json                │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  Keyword Filter                          │
│         Check for: urgent, exam, tutor, etc.            │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   Gemini AI Analysis                     │
│        "Is this a real student needing help?"           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  Discord Notification                    │
│           Send lead details via webhook                  │
└─────────────────────────────────────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `lead_sniper.py` | Main monitoring script |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for environment variables |
| `.env` | Your actual credentials (do not commit!) |
| `seen_posts.json` | Auto-created file tracking processed posts |

## Troubleshooting

### "GEMINI_API_KEY not set"
- Make sure you created a `.env` file from `.env.example`
- Verify the API key is correct and has no extra spaces

### "DISCORD_WEBHOOK_URL not set"
- Create a Discord webhook and add it to `.env`
- Make sure the URL is complete (starts with `https://discord.com/api/webhooks/`)

### Rate limiting
- Reddit may temporarily block requests if you check too frequently
- The script includes delays between requests to avoid this
- If you see 429 errors, increase `CHECK_INTERVAL_MINUTES`

### No posts found
- Some subreddits may have low activity
- Try running during peak hours (US evening time)
- Check if the subreddit names are correct

## Running as a Background Service

### Using screen (Linux/Mac)

```bash
screen -S leadsniper
python lead_sniper.py
# Press Ctrl+A, then D to detach
# Use 'screen -r leadsniper' to reattach
```

### Using nohup (Linux/Mac)

```bash
nohup python lead_sniper.py > output.log 2>&1 &
```

### Using systemd (Linux)

Create `/etc/systemd/system/leadsniper.service`:

```ini
[Unit]
Description=Math Lead Sniper
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python lead_sniper.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable leadsniper
sudo systemctl start leadsniper
```
