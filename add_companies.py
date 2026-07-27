import json
import re
import time
import os
import requests

CANDIDATES_PATH = "candidates.txt"
CONFIG_PATH = "companies.json"
HEADERS = {"User-Agent": "job-watcher-slug-finder/1.0"}


def check_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        return resp.status_code == 200
    except Exception:
        return False


def check_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        return resp.status_code == 200
    except Exception:
        return False


def check_ashby(slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        return resp.status_code == 200
    except Exception:
        return False


CHECKERS = [
    ("greenhouse", check_greenhouse),
    ("lever", check_lever),
    ("ashby", check_ashby),
]


def generate_candidates(name):
    base = name.strip()
    lower = base.lower()
    no_space = re.sub(r"\s+", "", lower)
    hyphenated = re.sub(r"\s+", "-", lower)
    no_punct = re.sub(r"[^a-z0-9\s]", "", lower)
    no_punct_no_space = re.sub(r"\s+", "", no_punct)
    first_word = lower.split()[0] if lower.split() else lower

    candidates = {
        no_space,
        hyphenated,
        no_punct_no_space,
        first_word,
        no_punct_no_space + "inc",
        no_punct_no_space + "hq",
    }
    return [c for c in candidates if c]


def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"{CONFIG_PATH} not found. Create it first.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def already_configured(config, name, ats, slug):
    for c in config.get("companies", []):
        if c["name"].strip().lower() == name.strip().lower():
            return True
        if c["ats"] == ats and c["slug"] == slug:
            return True
    return False


def main():
    if not os.path.exists(CANDIDATES_PATH):
        print(f"Create {CANDIDATES_PATH} with one company name per line first.")
        return

    with open(CANDIDATES_PATH, "r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    config = load_config()
    added = []
    not_found = []

    for name in names:
        print(f"\nSearching for: {name}")
        match_found = False
        candidates = generate_candidates(name)

        for slug in candidates:
            if match_found:
                break
            for ats_name, checker in CHECKERS:
                if checker(slug):
                    if already_configured(config, name, ats_name, slug):
                        print(f"  [SKIP] {ats_name}: {slug} — already in companies.json")
                        match_found = True
                        break
                    config["companies"].append({
                        "name": name,
                        "ats": ats_name,
                        "slug": slug,
                    })
                    print(f"  [ADDED] {ats_name}: {slug}")
                    added.append((name, ats_name, slug))
                    match_found = True
                    break
                time.sleep(0.3)

        if not match_found:
            not_found.append(name)
            print(f"  No match found. Tried: {sorted(candidates)}")

    save_config(config)

    print(f"\n{'='*50}")
    print(f"Added {len(added)} companies to {CONFIG_PATH}:")
    for name, ats, slug in added:
        print(f"  {name} ({ats}: {slug})")

    if not_found:
        print(f"\nCould not auto-resolve {len(not_found)} companies (check manually):")
        for name in not_found:
            print(f"  {name}")


if __name__ == "__main__":
    main()