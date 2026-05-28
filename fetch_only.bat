@echo off
REM fetch_only.bat — Run by Windows Task Scheduler for daily automated fetches.
REM Add this to Task Scheduler: Action → Start a program → full path to this file.
cd /d "%~dp0"
python -c "
import database, fetchers
database.init_db()
jobs, results = fetchers.fetch_all_jobs(7)
database.upsert_jobs(jobs)
database.purge_old_jobs(14)
print('Fetched', len(jobs), 'jobs')
for s, n in results.items(): print(f'  {s}: {n}')
"
