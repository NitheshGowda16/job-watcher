import json
import os
import requests

CONFIG_PATH = "companies.json"
HEADERS = {"User-Agent": "job-watcher-pruner/1.0"}


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


CHECKERS = {
    "greenhouse": check_greenhouse,
    "lever": check_lever,
    "ashby": check_ashby,
}