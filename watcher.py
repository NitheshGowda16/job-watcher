import json
import os
import sys
import time
import requests
from datetime import datetime, timezone

CONFIG_PATH = "companies.json"
STATE_PATH = "seen_jobs.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {"User-Agent": "job-watcher-script/1.0"}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fetch_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    results = []
    for j in jobs:
        results.append({
            "id": str(j["id"]),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
        })
    return results


def fetch_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    jobs = resp.json()
    results = []
    for j in jobs:
        results.append({
            "id": str(j.get("id")),
            "title": j.get("text", ""),
            "location": (j.get("categories") or {}).get("location", ""),
            "url": j.get("hostedUrl", ""),
        })
    return results


def fetch_ashby(slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    results = []
    for j in jobs:
        results.append({
            "id": str(j.get("id")),
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "url": j.get("jobUrl", ""),
        })
    return results


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


def matches_filters(job, keywords_include, keywords_exclude, locations_include):
    title = job["title"].lower()
    location = (job["location"] or "").lower()

    if keywords_exclude and any(kw.lower() in title for kw in keywords_exclude):
        return False

    if keywords_include and not any(kw.lower() in title for kw in keywords_include):
        return False

    if locations_include:
        if not any(loc.lower() in location for loc in locations_include):
            return False

    return True


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing, skipping notification.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, data=payload, timeout=20)
    if resp.status_code != 200:
        print(f"Telegram send failed: {resp.status_code} {resp.text}")


def main():
    config = load_json(CONFIG_PATH, None)
    if config is None:
        print(f"Missing {CONFIG_PATH}. Create it first.")
        sys.exit(1)

    state = load_json(STATE_PATH, {})
    keywords_include = config.get("keywords_include", [])
    keywords_exclude = config.get("keywords_exclude", [])
    locations_include = config.get("locations_include", [])

    new_count = 0

    for company in config.get("companies", []):
        name = company["name"]
        ats = company["ats"]
        slug = company["slug"]

        fetcher = FETCHERS.get(ats)
        if not fetcher:
            print(f"Unknown ATS type '{ats}' for {name}, skipping.")
            continue

        try:
            jobs = fetcher(slug)
        except Exception as e:
            print(f"Failed to fetch jobs for {name} ({ats}): {e}")
            continue

        seen_ids = set(state.get(name, []))
        current_ids = set()

        for job in jobs:
            current_ids.add(job["id"])
            if job["id"] in seen_ids:
                continue
            if not matches_filters(job, keywords_include, keywords_exclude, locations_include):
                continue

            message = (
                f"<b>{name}</b>: {job['title']}\n"
                f"{job['location']}\n"
                f"{job['url']}"
            )
            send_telegram(message)
            new_count += 1
            time.sleep(1)

        state[name] = list(current_ids)

    save_json(STATE_PATH, state)
    print(f"Run complete at {datetime.now(timezone.utc).isoformat()}. New matches: {new_count}")


if __name__ == "__main__":
    main()