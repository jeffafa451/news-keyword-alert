import json
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import requests

BASE_DIR = Path(__file__).resolve().parent
FEEDS_FILE = BASE_DIR / "feeds.txt"
SEEN_FILE = BASE_DIR / "seen_links.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

LOOKBACK_MINUTES = 10
MAX_ALERTS = 5


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


def parse_entry_datetime(entry):
    for field in ("published", "updated"):
        value = entry.get(field)
        if value:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass

    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    return None


def build_news_message(item):
    published_text = item["published_dt"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"🔔 이재용 신규 기사 발견\n\n"
        f"제목: {item['title']}\n"
        f"시각: {published_text}\n"
        f"링크: {item['link']}"
    )


def build_empty_message(now_utc):
    checked_text = now_utc.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"ℹ️ 이재용 뉴스 점검 완료\n\n"
        f"최근 {LOOKBACK_MINUTES}분 내 신규 기사 없음\n"
        f"점검 시각: {checked_text}"
    )


def main():
    feeds = load_lines(FEEDS_FILE)
    seen_links = load_seen_links()

    if not feeds:
        print("No feeds found.")
        return

    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(minutes=LOOKBACK_MINUTES)

    candidates = []
    new_seen = set(seen_links)

    for feed_url in feeds:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            if link in seen_links:
                continue

            published_dt = parse_entry_datetime(entry)
            if published_dt is None:
                continue

            if published_dt < cutoff:
                continue

            candidates.append(
                {
                    "title": title,
                    "link": link,
                    "published_dt": published_dt,
                }
            )

    candidates.sort(key=lambda x: x["published_dt"], reverse=True)

    selected = []
    selected_links = set()

    for item in candidates:
        if item["link"] in selected_links:
            continue
        selected.append(item)
        selected_links.add(item["link"])
        if len(selected) >= MAX_ALERTS:
            break

    if selected:
        for item in selected:
            send_telegram_message(build_news_message(item))
            new_seen.add(item["link"])
    else:
        send_telegram_message(build_empty_message(now_utc))

    save_seen_links(new_seen)
    print(f"Done. Sent {len(selected)} news alerts.")


if __name__ == "__main__":
    main()
