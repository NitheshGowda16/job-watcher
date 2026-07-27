import json
import requests

CONFIG_PATH = "companies.json"

HEADERS = {"User-Agent": "job-watcher-validator/1.0"}


def check_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    return resp.status_code == 200


def check_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    return resp.status_code == 200


def check_ashby(slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    return resp.status_code == 200


CHECKERS = {
    "greenhouse": check_greenhouse,
    "lever": check_lever,
    "ashby": check_ashby,
}


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    valid = []
    invalid = []

    for company in config.get("companies", []):
        name = company["name"]
        ats = company["ats"]
        slug = company["slug"]
        checker = CHECKERS.get(ats)

        if not checker:
            invalid.append((name, ats, slug, "unknown ATS type"))
            continue

        try:
            ok = checker(slug)
        except Exception as e:
            ok = False

        if ok:
            valid.append((name, ats, slug))
        else:
            invalid.append((name, ats, slug, "not found / wrong slug"))

    print(f"\nVALID ({len(valid)}):")
    for name, ats, slug in valid:
        print(f"  [OK] {name} ({ats}: {slug})")

    print(f"\nINVALID ({len(invalid)}) — remove or fix these in companies.json:")
    for name, ats, slug, reason in invalid:
        print(f"  [FAIL] {name} ({ats}: {slug}) — {reason}")


if __name__ == "__main__":
    main()