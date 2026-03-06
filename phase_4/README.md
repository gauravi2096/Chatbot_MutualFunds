# Phase 4 — Scheduler for Daily Live Data

Runs the data-ingestion pipeline daily so that the structured store (funds.json), vector store (chroma), and **last_data_update** timestamp stay up to date. On success, the registry and funds.json are updated; on failure, the job logs and exits non-zero (previous data is kept).

## Components

| Component | Responsibility |
|-----------|----------------|
| **run_daily_update.py** | Entry point: calls Phase 1 `run_ingestion()`. Exits 0 on success, 1 on failure. |
| **GitHub Actions** | Workflow runs daily at 10:00 AM IST; runs ingestion and commits updated data. |

## Run locally (manual)

From project root:

```bash
# Install deps and Playwright browser
pip install -r phase_0/requirements.txt -r phase_1/requirements.txt
playwright install chromium

# Run the pipeline
python phase_4/run_daily_update.py
```

Exit code 0 = success (funds.json, source_registry.json, and chroma updated). Exit code 1 = failure (no valid records or exception).

## GitHub Actions (daily 10 AM)

The workflow `.github/workflows/daily-data-update.yml`:

- **Schedule**: 10:00 AM IST (04:30 UTC) every day.
- **Steps**: Checkout → Set up Python → Install phase_0 + phase_1 deps → Playwright install chromium → Run `phase_4/run_daily_update.py` → Commit and push updated `phase_1/data/funds.json`, `phase_0/data/source_registry.json`, and `phase_1/data/chroma`.

Ensure the repo has write access for the workflow (default `GITHUB_TOKEN` can push when the workflow is in the same repo).

## Verifying the scheduler

1. **Trigger manually**: GitHub → Actions → "Daily data update" → "Run workflow" (workflow_dispatch).
2. **Confirm success**: The run should complete with a green check; job "update-data" runs ingestion then commits and pushes.
3. **Verify committed files**: After a successful run, the latest commit on `main` (by `github-actions[bot]`) should update:
   - `phase_1/data/funds.json` — `last_updated` timestamp will change.
   - `phase_0/data/source_registry.json` — `last_data_update` updated.
   - `phase_1/data/chroma` — vector store files updated.
4. **Check timestamp**: In `phase_1/data/funds.json`, the top-level `last_updated` field should reflect the run time (e.g. after a 10 AM IST run, it will show that date/time).

From CLI: `gh run list --workflow="Daily data update"` and `gh run view <run-id>` to inspect; `git pull` then inspect the latest commit and the three paths above.

## Monitoring

- Logs: Check workflow run logs in the Actions tab, or local stdout when run manually.
- On partial failure (e.g. some funds fail to scrape), the pipeline still saves whatever records succeeded and updates the timestamp; failed sources are skipped and logged.
