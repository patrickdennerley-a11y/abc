#!/usr/bin/env python3
"""
Math Lead Sniper - Monitors Reddit and Google Alerts for math tutoring leads.
Sends qualified leads to Discord via webhook.
"""

import os
import time
import requests
import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
GOOGLE_ALERTS_RSS = os.getenv('GOOGLE_ALERTS_RSS', '')

# Subreddits to monitor
SUBREDDITS = ['HomeworkHelp', 'Calculus', 'learnmath', 'MathHelp', 'Precalculus']

# Request headers for Reddit
HEADERS = {'User-Agent': 'MathLeadSniper/1.0 (Educational Lead Finder)'}

# Trigger keywords (case-insensitive)
TRIGGER_KEYWORDS = [
    'urgent', 'exam', 'tutor', 'fail', 'due', 'stuck', 'help', 'tomorrow',
    'tonight', 'asap', 'struggling', 'desperate', 'need help', "don't understand",
    'confused', 'failing', 'test', 'quiz', 'midterm', 'final', 'assignment',
    'homework', 'please help', 'anyone help', 'can someone', 'i need'
]

# Track seen posts and cooldowns
seen_post_ids = set()
url_cooldowns = {}  # url -> datetime when cooldown expires

# Gemini system instruction
GEMINI_SYSTEM_INSTRUCTION = """You are a lead qualifier for a math tutor. Respond with ONLY the word YES or NO.

Return YES if: The user is a student explicitly asking for help with math, struggling with homework/exams, or seeking tutoring.

Return NO if: It's spam, an ad, a bot, a meme, a general discussion, someone just venting with no intent to get help, or homework help that's already been answered."""


def setup_gemini():
    """Configure the Gemini AI client."""
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set in environment")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        system_instruction=GEMINI_SYSTEM_INSTRUCTION
    )
    return model


def get_new_reddit_posts(subreddit):
    """Fetch new posts from a subreddit using JSON endpoint."""
    url = f"https://old.reddit.com/r/{subreddit}/new.json?limit=25"

    for attempt in range(4):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('children', [])
            elif response.status_code == 429:
                # Rate limited - exponential backoff
                wait_time = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  Error fetching r/{subreddit}: HTTP {response.status_code}")
                return []

        except requests.exceptions.RequestException as e:
            wait_time = 2 ** (attempt + 1)
            print(f"  Request error for r/{subreddit}: {e}")
            if attempt < 3:
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)

    return []


def get_google_alerts_entries():
    """Fetch entries from Google Alerts RSS feeds."""
    if not GOOGLE_ALERTS_RSS:
        return []

    entries = []
    rss_urls = [url.strip() for url in GOOGLE_ALERTS_RSS.split(',') if url.strip()]

    for rss_url in rss_urls:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                entries.append({
                    'id': entry.get('id', entry.get('link', '')),
                    'title': entry.get('title', ''),
                    'content': entry.get('summary', ''),
                    'url': entry.get('link', ''),
                    'source': 'Google Alerts'
                })
        except Exception as e:
            print(f"  Error parsing RSS feed: {e}")

    return entries


def contains_trigger_keyword(text):
    """Check if text contains any trigger keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in TRIGGER_KEYWORDS)


def is_url_on_cooldown(url):
    """Check if URL is on cooldown (processed within last hour)."""
    if url in url_cooldowns:
        if datetime.now() < url_cooldowns[url]:
            return True
        else:
            del url_cooldowns[url]
    return False


def set_url_cooldown(url):
    """Set 1-hour cooldown for a URL."""
    url_cooldowns[url] = datetime.now() + timedelta(hours=1)


def qualify_lead_with_gemini(model, title, content):
    """Use Gemini AI to qualify if this is a good lead."""
    if model is None:
        return True  # If no API key, pass everything through

    prompt = f"Title: {title}\n\nContent: {content[:1000]}"

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            result = response.text.strip().upper()
            return result == 'YES'
        except Exception as e:
            wait_time = 2 ** (attempt + 1)
            print(f"  Gemini error: {e}")
            if attempt < 2:
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)

    return False


def send_to_discord(title, content, url, source):
    """Send qualified lead to Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set in environment")
        return False

    # Truncate content for embed
    content_snippet = content[:300] + "..." if len(content) > 300 else content

    embed = {
        "title": f"🎯 New Math Lead from {source}",
        "description": f"**{title}**\n\n{content_snippet}",
        "url": url,
        "color": 5814783,  # Blue color
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Math Lead Sniper"}
    }

    payload = {"embeds": [embed]}

    for attempt in range(4):
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 204]:
                return True
            elif response.status_code == 429:
                # Rate limited
                retry_after = response.json().get('retry_after', 2 ** (attempt + 1))
                print(f"  Discord rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
            else:
                print(f"  Discord error: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            wait_time = 2 ** (attempt + 1)
            print(f"  Discord request error: {e}")
            if attempt < 3:
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)

    return False


def process_reddit_post(post_data, model):
    """Process a single Reddit post."""
    post = post_data.get('data', {})
    post_id = post.get('id', '')
    title = post.get('title', '')
    selftext = post.get('selftext', '')
    permalink = post.get('permalink', '')
    subreddit = post.get('subreddit', '')

    # Skip if already seen
    if post_id in seen_post_ids:
        return False

    seen_post_ids.add(post_id)

    # Build full URL
    url = f"https://reddit.com{permalink}"

    # Skip if on cooldown
    if is_url_on_cooldown(url):
        return False

    # Combine title and content for keyword check
    full_text = f"{title} {selftext}"

    # Check for trigger keywords
    if not contains_trigger_keyword(full_text):
        return False

    print(f"  Found potential lead in r/{subreddit}: {title[:50]}...")
    print("  Checking with AI...")

    # Qualify with Gemini
    if not qualify_lead_with_gemini(model, title, selftext):
        print("  AI says NO - skipping")
        return False

    print("  AI says YES - sending to Discord!")

    # Send to Discord
    if send_to_discord(title, selftext, url, f"r/{subreddit}"):
        set_url_cooldown(url)
        print("  Lead sent to Discord!")
        return True

    return False


def process_google_alert(entry, model):
    """Process a single Google Alert entry."""
    entry_id = entry.get('id', '')
    title = entry.get('title', '')
    content = entry.get('content', '')
    url = entry.get('url', '')

    # Skip if already seen
    if entry_id in seen_post_ids:
        return False

    seen_post_ids.add(entry_id)

    # Skip if on cooldown
    if is_url_on_cooldown(url):
        return False

    # Combine title and content for keyword check
    full_text = f"{title} {content}"

    # Check for trigger keywords
    if not contains_trigger_keyword(full_text):
        return False

    print(f"  Found potential lead from Google Alerts: {title[:50]}...")
    print("  Checking with AI...")

    # Qualify with Gemini
    if not qualify_lead_with_gemini(model, title, content):
        print("  AI says NO - skipping")
        return False

    print("  AI says YES - sending to Discord!")

    # Send to Discord
    if send_to_discord(title, content, url, "Google Alerts"):
        set_url_cooldown(url)
        print("  Lead sent to Discord!")
        return True

    return False


def check_reddit(model):
    """Check all subreddits for new posts."""
    total_leads = 0

    for subreddit in SUBREDDITS:
        print(f"Checking r/{subreddit}...")
        posts = get_new_reddit_posts(subreddit)

        for post in posts:
            if process_reddit_post(post, model):
                total_leads += 1

        # Be nice to Reddit - wait between subreddits
        time.sleep(2)

    return total_leads


def check_google_alerts(model):
    """Check Google Alerts RSS feeds."""
    if not GOOGLE_ALERTS_RSS:
        return 0

    print("Checking Google Alerts...")
    entries = get_google_alerts_entries()
    total_leads = 0

    for entry in entries:
        if process_google_alert(entry, model):
            total_leads += 1

    return total_leads


def main():
    """Main loop."""
    print("=" * 50)
    print("Math Lead Sniper - Starting up...")
    print("=" * 50)

    # Validate configuration
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set - AI filtering disabled")
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set - cannot send leads!")
        print("Please set DISCORD_WEBHOOK_URL in your .env file")
        return

    # Setup Gemini
    model = setup_gemini()

    print(f"\nMonitoring {len(SUBREDDITS)} subreddits: {', '.join(SUBREDDITS)}")
    if GOOGLE_ALERTS_RSS:
        rss_count = len([u for u in GOOGLE_ALERTS_RSS.split(',') if u.strip()])
        print(f"Monitoring {rss_count} Google Alerts RSS feed(s)")
    print("\nPress Ctrl+C to stop.\n")

    reddit_check_interval = 120  # 2 minutes
    rss_check_interval = 300     # 5 minutes

    last_reddit_check = 0
    last_rss_check = 0

    try:
        while True:
            current_time = time.time()

            # Check Reddit every 2 minutes
            if current_time - last_reddit_check >= reddit_check_interval:
                leads = check_reddit(model)
                if leads > 0:
                    print(f"\n>>> Found {leads} new lead(s) from Reddit!\n")
                last_reddit_check = current_time

            # Check RSS every 5 minutes
            if current_time - last_rss_check >= rss_check_interval:
                leads = check_google_alerts(model)
                if leads > 0:
                    print(f"\n>>> Found {leads} new lead(s) from Google Alerts!\n")
                last_rss_check = current_time

            # Sleep for a bit before checking again
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\nShutting down Math Lead Sniper...")
        print(f"Processed {len(seen_post_ids)} unique posts this session.")
        print("Goodbye!")


if __name__ == "__main__":
    main()
