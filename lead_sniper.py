#!/usr/bin/env python3
"""
Reddit Math Tutoring Lead Monitor

Monitors Reddit for math tutoring opportunities, filters with Gemini AI,
and sends notifications to Discord.
"""

import os
import re
import json
import time
import random
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

SUBREDDITS = ["HomeworkHelp", "Calculus", "LearnMath", "MathHelp", "PreCalculus"]

TRIGGER_KEYWORDS = [
    "urgent", "exam", "tutor", "fail", "due", "stuck",
    "help", "tomorrow", "tonight", "asap", "struggling"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# File to store seen post IDs and cooldowns
SEEN_POSTS_FILE = Path("seen_posts.json")
COOLDOWN_HOURS = 1
CHECK_INTERVAL_MINUTES = 5


def load_seen_posts():
    """Load seen posts from file."""
    if SEEN_POSTS_FILE.exists():
        try:
            with open(SEEN_POSTS_FILE, "r") as f:
                data = json.load(f)
                # Clean up old cooldowns (older than 24 hours)
                cutoff = datetime.now().timestamp() - (24 * 3600)
                data["cooldowns"] = {
                    k: v for k, v in data.get("cooldowns", {}).items()
                    if v > cutoff
                }
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"seen_ids": [], "cooldowns": {}}


def save_seen_posts(data):
    """Save seen posts to file."""
    # Keep only last 1000 IDs to prevent file bloat
    data["seen_ids"] = data["seen_ids"][-1000:]
    with open(SEEN_POSTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_on_cooldown(url, cooldowns):
    """Check if a URL is on cooldown."""
    if url in cooldowns:
        cooldown_until = cooldowns[url]
        if datetime.now().timestamp() < cooldown_until:
            return True
    return False


def set_cooldown(url, cooldowns):
    """Set cooldown for a URL."""
    cooldowns[url] = (datetime.now() + timedelta(hours=COOLDOWN_HOURS)).timestamp()


def fetch_with_retry(url, headers, max_retries=3):
    """Fetch URL with retry logic and exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"  [!] Request failed, retrying in {wait_time:.1f}s... ({e})")
                time.sleep(wait_time)
            else:
                print(f"  [!] Request failed after {max_retries} attempts: {e}")
                return None
    return None


def fetch_subreddit_posts(subreddit):
    """Fetch new posts from a subreddit using public JSON endpoint."""
    url = f"https://old.reddit.com/r/{subreddit}/new.json?limit=25"
    headers = {"User-Agent": USER_AGENT}

    response = fetch_with_retry(url, headers)
    if not response:
        return []

    try:
        data = response.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            post_data = child.get("data", {})
            posts.append({
                "id": post_data.get("id"),
                "title": post_data.get("title", ""),
                "selftext": post_data.get("selftext", ""),
                "url": f"https://reddit.com{post_data.get('permalink', '')}",
                "subreddit": subreddit,
                "created_utc": post_data.get("created_utc", 0),
                "author": post_data.get("author", "[deleted]")
            })
        return posts
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [!] Error parsing response from r/{subreddit}: {e}")
        return []


def contains_trigger_keyword(text):
    """Check if text contains any trigger keywords."""
    text_lower = text.lower()
    for keyword in TRIGGER_KEYWORDS:
        if re.search(r'\b' + keyword + r'\b', text_lower):
            return keyword
    return None


def analyze_with_gemini(title, selftext, subreddit):
    """Use Gemini AI to determine if this is a real student needing help."""
    if not GEMINI_API_KEY:
        print("  [!] GEMINI_API_KEY not set, skipping AI analysis")
        return True  # Default to true if no API key

    prompt = f"""Analyze this Reddit post from r/{subreddit} and determine if it's from a real student who needs math tutoring or homework help.

Title: {title}

Post content: {selftext[:1000] if selftext else "(no content)"}

Consider:
- Is this a genuine student struggling with math?
- Are they asking for help with homework, exams, or concepts?
- Would they benefit from a tutor?

Reply with ONLY "YES" if this is a real student needing help, or "NO" if it's spam, a joke, someone offering services, or not a genuine help request."""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        result = response.text.strip().upper()
        return result.startswith("YES")
    except Exception as e:
        print(f"  [!] Gemini API error: {e}")
        return True  # Default to true on error to not miss leads


def send_discord_notification(post, keyword):
    """Send a notification to Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("  [!] DISCORD_WEBHOOK_URL not set, skipping notification")
        return False

    # Create snippet from title and selftext
    snippet = post["title"]
    if post["selftext"]:
        snippet += f"\n\n{post['selftext'][:300]}..."

    embed = {
        "title": f"🎯 Math Lead from r/{post['subreddit']}",
        "description": snippet[:500],
        "url": post["url"],
        "color": 0x00ff00,  # Green
        "fields": [
            {"name": "Keyword", "value": keyword, "inline": True},
            {"name": "Author", "value": f"u/{post['author']}", "inline": True},
            {"name": "Subreddit", "value": f"r/{post['subreddit']}", "inline": True}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }

    payload = {
        "username": "Math Lead Sniper",
        "embeds": [embed]
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  [!] Discord webhook error: {e}")
        return False


def process_posts(posts, seen_data):
    """Process a list of posts, filtering and notifying."""
    new_leads = 0

    for post in posts:
        # Skip if already seen
        if post["id"] in seen_data["seen_ids"]:
            continue

        # Mark as seen
        seen_data["seen_ids"].append(post["id"])

        # Check cooldown
        if is_on_cooldown(post["url"], seen_data["cooldowns"]):
            continue

        # Check for trigger keywords
        combined_text = f"{post['title']} {post['selftext']}"
        keyword = contains_trigger_keyword(combined_text)

        if not keyword:
            continue

        print(f"  [*] Found keyword '{keyword}' in: {post['title'][:60]}...")

        # Analyze with Gemini
        print(f"  [*] Analyzing with Gemini AI...")
        is_lead = analyze_with_gemini(post["title"], post["selftext"], post["subreddit"])

        if not is_lead:
            print(f"  [-] Gemini says NOT a real lead, skipping")
            continue

        print(f"  [+] Gemini confirmed as REAL lead!")

        # Send Discord notification
        if send_discord_notification(post, keyword):
            print(f"  [+] Discord notification sent!")
            new_leads += 1
            set_cooldown(post["url"], seen_data["cooldowns"])

        # Small delay between processing
        time.sleep(0.5)

    return new_leads


def run_check():
    """Run a single check of all subreddits."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting check...")
    print(f"{'='*60}")

    seen_data = load_seen_posts()
    total_leads = 0

    for i, subreddit in enumerate(SUBREDDITS):
        print(f"\n[{i+1}/{len(SUBREDDITS)}] Checking r/{subreddit}...")

        posts = fetch_subreddit_posts(subreddit)
        print(f"  [*] Fetched {len(posts)} posts")

        if posts:
            leads = process_posts(posts, seen_data)
            total_leads += leads

        # Delay between subreddits (2-3 seconds)
        if i < len(SUBREDDITS) - 1:
            delay = random.uniform(2, 3)
            print(f"  [*] Waiting {delay:.1f}s before next subreddit...")
            time.sleep(delay)

    save_seen_posts(seen_data)

    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check complete!")
    print(f"  Total new leads found: {total_leads}")
    print(f"  Total posts tracked: {len(seen_data['seen_ids'])}")
    print(f"{'='*60}")

    return total_leads


def main():
    """Main entry point - runs continuous monitoring."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           Math Lead Sniper - Reddit Monitor                   ║
║                                                               ║
║  Monitoring: HomeworkHelp, Calculus, LearnMath,              ║
║              MathHelp, PreCalculus                            ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Validate configuration
    if not GEMINI_API_KEY:
        print("[!] WARNING: GEMINI_API_KEY not set - AI filtering disabled")
    else:
        print("[+] Gemini API key configured")

    if not DISCORD_WEBHOOK_URL:
        print("[!] WARNING: DISCORD_WEBHOOK_URL not set - notifications disabled")
    else:
        print("[+] Discord webhook configured")

    print(f"\n[*] Check interval: {CHECK_INTERVAL_MINUTES} minutes")
    print(f"[*] Cooldown period: {COOLDOWN_HOURS} hour(s)")
    print(f"[*] Trigger keywords: {', '.join(TRIGGER_KEYWORDS)}")
    print("\n[*] Press Ctrl+C to stop\n")

    try:
        while True:
            run_check()
            print(f"\n[*] Next check in {CHECK_INTERVAL_MINUTES} minutes...")
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down gracefully...")
        print("[*] Goodbye!")


if __name__ == "__main__":
    main()
