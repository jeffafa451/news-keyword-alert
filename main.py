import json
import os
from pathlib import Path

import feedparser
import requests

BASE_DIR = Path(__file__).resolve().parent
FEEDS_FILE = BASE_DIR / "feeds.txt"
KEYWORDS_FILE = BASE_DIR / "keywords.txt"
SEEN_FILE = BASE_DIR / "seen_links.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def load_lines(path: Path):
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_seen_links():
    if not SEEN_FILE.exists():
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data)
    except Exception:
        return set()


def save_seen_links(seen_links):
    SEEN_FILE.write_text(
        json.dumps(sorted(list(seen_links)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_telegram_message(text: str):
    response = requests.post(
        TELEGRAM_API,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    response.raise_for_status()


def matches_keywords(text: str, keywords):
    lowered = text.lower()
    return [kw for kw in keywords if kw.lower() in lowered]


def main():
    feeds = load_lines(FEEDS_FILE)
    keywords = load_lines(KEYWORDS_FILE)
    seen_links = load_seen_links()

    if not feeds:
        print("No feeds found.")
        return

    if not keywords:
        print("No keywords found.")
        return

    new_seen = set(seen_links)
    alerts = []

    for feed_url in feeds:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            link = entry.get("link", "").strip()
            published = entry.get("published", "").strip()

            if not link or link in seen_links:
                continue

            haystack = f"{title}\n{summary}"
            matched = matches_keywords(haystack, keywords)

            if matched:
                alerts.append(
                    {
                        "title": title,
                        "link": link,
                        "published": published,
                        "matched": matched,
                    }
                )

            new_seen.add(link)

    for item in alerts:
        msg = (
            f"🔔 키워드 기사 발견\n\n"
            f"키워드: {', '.join(item['matched'])}\n"
            f"제목: {item['title']}\n"
            f"일시: {item['published']}\n"
            f"링크: {item['link']}"
        )
        send_telegram_message(msg)

    save_seen_links(new_seen)
    print(f"Done. Sent {len(alerts)} alerts.")


if __name__ == "__main__":
    main()
