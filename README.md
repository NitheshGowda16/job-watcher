# Job Watcher

Automated job-posting monitor that watches company career pages directly (via their ATS APIs) and sends a Telegram notification within minutes of a new, relevant posting going live — running on a schedule in the cloud, independent of your laptop.

## Why this exists

Job boards like LinkedIn and Indeed index company postings on a delayed batch schedule (often 12–48 hours behind). This tool skips the aggregator entirely and queries the same APIs those career pages use internally — Greenhouse, Lever, and Ashby — so you see new postings close to the moment they're published.

---

## Architecture

```
┌─────────────────────┐
│  GitHub Actions     │  Scheduled trigger, every 20 minutes (cron)
│  (watcher.yml)      │  Also runnable manually via "Run workflow"
└──────────┬──────────┘
           │ checks out repo, installs deps
           ▼
┌─────────────────────┐
│  watcher.py         │  1. Reads companies.json (config)
│                     │  2. Fetches jobs per company (Greenhouse /
│                     │     Lever / Ashby public APIs)
│                     │  3. Filters: keyword, location, age (<=48h)
│                     │  4. Diffs against seen_jobs.json (state)
│                     │  5. Sends Telegram message for new matches
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Telegram Bot API   │  Pushes notification to your phone/desktop
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  seen_jobs.json     │  Committed back to the repo by the workflow
│  (state, in-repo)   │  so the next run knows what's already notified
└─────────────────────┘

┌─────────────────────┐
│  GitHub Actions     │  Scheduled trigger, weekly (Monday 6 AM UTC)
│  (maintenance.yml)  │  Also runnable manually
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  remove_stale.py    │  Validates every company's slug, prunes dead
│                     │  ones, writes result back to companies.json
└─────────────────────┘
```

No server to run or pay for — GitHub Actions provides the compute on its schedule, and the repo itself is the database (via the committed state file).

---

## Files

| File | Purpose |
|---|---|
| `watcher.py` | Main script — fetch, filter, diff, notify |
| `companies.json` | Config: target companies, keyword/location/age filters |
| `seen_jobs.json` | Auto-generated/auto-updated state — do not edit by hand |
| `validate_slugs.py` | Checks every configured company's slug still resolves; reports only, doesn't change the file |
| `remove_stale.py` | Auto-removes companies whose slug no longer resolves, writes result back to `companies.json` |
| `add_companies.py` | Reads `candidates.txt`, auto-discovers + adds valid slugs to `companies.json` |
| `candidates.txt` | Plain list of company names you want to try adding (input to `add_companies.py`) |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Excludes venv, cache, and local secrets from Git |
| `.github/workflows/watcher.yml` | Schedule definition for the main watcher (every 20 min) |
| `.github/workflows/maintenance.yml` | Schedule definition for weekly stale-slug pruning |

---

## Configuration reference (`companies.json`)

```json
{
  "max_age_hours": 48,
  "keywords_include": ["software engineer", "sde", "full stack", ...],
  "keywords_exclude": ["staff", "principal", "director", "intern", ...],
  "locations_include": ["remote", "texas", "california", ...],
  "companies": [
    {"name": "Stripe", "ats": "greenhouse", "slug": "stripe"}
  ]
}
```

- **`max_age_hours`** — postings older than this are skipped. Greenhouse uses its `updated_at` field as a freshness proxy (can occasionally reflect an edit rather than the original post date); Lever and Ashby use exact creation/publish timestamps.
- **`keywords_include`** — a job title must contain at least one of these (case-insensitive).
- **`keywords_exclude`** — a job title containing any of these is dropped, even if it matched `keywords_include`.
- **`locations_include`** — a job's location must contain at least one of these strings.
- **`companies`** — each entry needs `name`, `ats` (`greenhouse` / `lever` / `ashby`), and `slug` (the company's identifier in that ATS's API).

---

## Operating workflow

### Adding new companies (no manual JSON editing)
1. Add company names, one per line, to `candidates.txt`.
2. Run:
```powershell
   python add_companies.py
```
3. It live-tests common slug variations against all three ATS APIs and appends confirmed matches directly to `companies.json`. Anything it can't resolve is printed at the end for a manual look.
4. Commit and push:
```powershell
   git add companies.json
   git commit -m "Add more target companies"
   git push
```

### Periodic health check (pruning)
Slugs occasionally stop resolving (company switches ATS providers, board renamed, etc.). Two options:

- **Manual**: `python validate_slugs.py` — reports failures for you to review before editing `companies.json` by hand.
- **Automatic**: `python remove_stale.py` — validates and immediately writes the pruned list back to `companies.json`, no manual edits needed.

If `.github/workflows/maintenance.yml` is set up, this runs automatically every Monday and commits the pruned config — no local action needed at all.

### Tuning filters
Edit `keywords_include`, `keywords_exclude`, `locations_include`, or `max_age_hours` directly in `companies.json`, then commit and push. No code changes needed for filter tuning.

### Manually triggering a run
Repo page → **Actions** tab → **Job Watcher** workflow → **Run workflow**. Useful for testing after a config change without waiting for the next scheduled tick. The same applies to the **Job Watcher Maintenance** workflow if you want to prune on demand.

### Monitoring the automation
Repo page → **Actions** tab shows every past run (both workflows), green/red status, and full logs (including any fetch failures per company, which print to the log without stopping the rest of the run).

---

## Local setup (one-time)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:TELEGRAM_BOT_TOKEN="your_token_here"
$env:TELEGRAM_CHAT_ID="your_chat_id_here"

python watcher.py
```

## Cloud setup (one-time)

1. Push the repo to GitHub (private recommended).
2. Repo → **Settings → Secrets and variables → Actions** → add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. `.github/workflows/watcher.yml` handles notifications — runs every 20 minutes automatically once pushed.
4. `.github/workflows/maintenance.yml` handles pruning — runs weekly automatically once pushed.

---

## Design notes / known limitations

- **No official slug directory exists** for Greenhouse/Lever/Ashby — `add_companies.py` and `remove_stale.py` exist specifically to make slug discovery and cleanup self-service and self-correcting rather than relying on a static list that will drift out of date.
- **Slug drift is self-healing**: `add_companies.py` discovers new slugs, `remove_stale.py` (optionally on a weekly schedule) prunes dead ones — the config maintains itself without manual JSON edits in either direction.
- **Freshness filtering is best-effort for Greenhouse** specifically, since `updated_at` isn't guaranteed to equal the original post date.
- **State is repo-committed**, not a database — fine at this scale (dozens of companies, one user), but not designed to scale to hundreds of watchers or multiple users.
- **Coverage gap**: companies on Workday, iCIMS, SmartRecruiters, or custom career-page systems aren't covered by this script's three fetchers. Extending to Workday is possible but non-trivial (no clean public JSON API per tenant) — worth doing only for a specific must-watch company.
- **Cron timing isn't exact** — GitHub Actions scheduled workflows can be delayed a few minutes under platform load; treat the 20-minute and weekly intervals as approximate, not guaranteed.
- **Discovering new companies still requires a human decision** — `add_companies.py` needs names in `candidates.txt` before it can act; deciding *which* companies belong on that list isn't automatable.