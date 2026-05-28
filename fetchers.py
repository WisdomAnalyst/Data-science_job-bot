"""
fetchers.py — Job source connectors for DS Job Bot.

Free (no key):   Remotive, Arbeitnow, We Work Remotely RSS
Needs free key:  Adzuna, JSearch (RapidAPI → LinkedIn/Indeed/Glassdoor), Reed UK
"""

import time
import json
import calendar
import requests
import feedparser
from datetime import datetime, timezone
from pathlib import Path

from utils import (
    detect_level, detect_region, detect_nigeria_friendly,
    is_within_days, parse_date, is_data_science_role,
    clean_description, generate_id,
)

CONFIG_PATH = Path(__file__).parent / "config.json"
HEADERS = {'User-Agent': 'DSJobBot/2.0 (+https://github.com/dsbot)'}

# ── Config loader ────────────────────────────────────────────────────────────

def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"api_keys": {}, "settings": {"days_back": 7}}


# ════════════════════════════════════════════════════════════════════════════
# SOURCE 1 · Remotive  (free, no key)
# ════════════════════════════════════════════════════════════════════════════

def fetch_remotive(days_back: int = 7) -> list:
    """Remote data science jobs from Remotive public API."""
    jobs = []
    for category in ['data-science', 'software-dev']:
        try:
            url = f"https://remotive.com/api/remote-jobs?category={category}&limit=100"
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()

            for job in r.json().get('jobs', []):
                title = job.get('title', '')
                desc  = clean_description(job.get('description', ''))
                if not is_data_science_role(title, desc):
                    continue

                posted = parse_date(job.get('publication_date', ''))
                if not is_within_days(posted, days_back):
                    continue

                location = job.get('candidate_required_location', 'Worldwide')
                jobs.append({
                    'id':              generate_id('remotive', str(job['id'])),
                    'title':           title,
                    'company':         job.get('company_name', 'Unknown'),
                    'location':        location,
                    'region':          detect_region(location),
                    'level':           detect_level(title, desc),
                    'job_type':        job.get('job_type', 'full_time'),
                    'description':     desc,
                    'apply_url':       job.get('url', ''),
                    'source':          'Remotive',
                    'posted_date':     posted.isoformat() if posted else datetime.now(timezone.utc).isoformat(),
                    'is_remote':       True,
                    'nigeria_friendly': detect_nigeria_friendly(location, desc),
                    'tags':            job.get('tags', []),
                    'salary':          job.get('salary', ''),
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [Remotive] {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# SOURCE 2 · Arbeitnow  (free, no key — European + remote)
# ════════════════════════════════════════════════════════════════════════════

def fetch_arbeitnow(days_back: int = 7) -> list:
    """Jobs from Arbeitnow (strong in Europe + remote)."""
    jobs = []
    for query in ['data+scientist', 'machine+learning', 'data+science', 'AI+engineer']:
        try:
            url = f"https://www.arbeitnow.com/api/job-board-api?search={query}"
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()

            for job in r.json().get('data', []):
                title = job.get('title', '')
                desc  = clean_description(job.get('description', ''))
                if not is_data_science_role(title, desc):
                    continue

                posted = parse_date(job.get('created_at', job.get('posted_at', '')))
                if posted and not is_within_days(posted, days_back):
                    continue

                location  = job.get('location', 'Remote')
                is_remote = bool(job.get('remote', False))
                region    = 'Remote' if is_remote else detect_region(location)

                jobs.append({
                    'id':              generate_id('arbeitnow', str(job.get('slug', job.get('id', title[:20])))),
                    'title':           title,
                    'company':         job.get('company_name', 'Unknown'),
                    'location':        location,
                    'region':          region,
                    'level':           detect_level(title, desc),
                    'job_type':        'full_time',
                    'description':     desc,
                    'apply_url':       job.get('url', ''),
                    'source':          'Arbeitnow',
                    'posted_date':     posted.isoformat() if posted else datetime.now(timezone.utc).isoformat(),
                    'is_remote':       is_remote,
                    'nigeria_friendly': detect_nigeria_friendly('worldwide' if is_remote else location, desc),
                    'tags':            job.get('tags', []),
                    'salary':          '',
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [Arbeitnow] {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# SOURCE 3 · We Work Remotely  (free RSS)
# ════════════════════════════════════════════════════════════════════════════

def fetch_weworkremotely(days_back: int = 7) -> list:
    """Remote jobs from We Work Remotely RSS feeds."""
    jobs = []
    feeds = [
        'https://weworkremotely.com/categories/remote-data-science-jobs.rss',
        'https://weworkremotely.com/categories/remote-programming-jobs.rss',
    ]

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                raw_title = entry.get('title', '')
                desc      = clean_description(entry.get('summary', ''))

                # Separate "Company | Title" format used by WWR
                company, title = '', raw_title
                if ' | ' in raw_title:
                    parts   = raw_title.split(' | ')
                    company = parts[0].strip()
                    title   = parts[-1].strip()

                if not is_data_science_role(title, desc):
                    continue

                posted = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    ts     = calendar.timegm(entry.published_parsed)
                    posted = datetime.fromtimestamp(ts, tz=timezone.utc)

                if posted and not is_within_days(posted, days_back):
                    continue

                raw_id = entry.get('id', entry.get('link', title))[:50]
                jobs.append({
                    'id':              generate_id('wwr', raw_id),
                    'title':           title,
                    'company':         company,
                    'location':        'Worldwide',
                    'region':          'Worldwide',
                    'level':           detect_level(title, desc),
                    'job_type':        'full_time',
                    'description':     desc,
                    'apply_url':       entry.get('link', ''),
                    'source':          'WeWorkRemotely',
                    'posted_date':     posted.isoformat() if posted else datetime.now(timezone.utc).isoformat(),
                    'is_remote':       True,
                    'nigeria_friendly': True,
                    'tags':            [],
                    'salary':          '',
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [WeWorkRemotely] {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# SOURCE 4 · Adzuna  (free key — US, UK, Canada, Europe)
# ════════════════════════════════════════════════════════════════════════════

def fetch_adzuna(days_back: int = 7) -> list:
    """Major job aggregator covering US, UK, Canada, Europe."""
    cfg     = load_config()
    app_id  = cfg.get('api_keys', {}).get('adzuna_app_id', '')
    app_key = cfg.get('api_keys', {}).get('adzuna_app_key', '')
    if not app_id or not app_key:
        print("  [Adzuna] Keys not set in config.json — skipping.")
        return []

    jobs = []
    countries = [
        ('us', 'USA'), ('gb', 'UK'), ('ca', 'Canada'),
        ('de', 'Europe'), ('nl', 'Europe'), ('fr', 'Europe'),
    ]

    for code, region in countries:
        for query in ['data scientist', 'machine learning engineer']:
            try:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/{code}/search/1"
                    f"?app_id={app_id}&app_key={app_key}"
                    f"&what={query.replace(' ', '+')}"
                    f"&max_days_old={days_back}&results_per_page=20"
                    f"&content-type=application%2Fjson"
                )
                r = requests.get(url, headers=HEADERS, timeout=30)
                r.raise_for_status()

                for job in r.json().get('results', []):
                    title = job.get('title', '')
                    desc  = clean_description(job.get('description', ''))
                    if not is_data_science_role(title, desc):
                        continue

                    posted   = parse_date(job.get('created', ''))
                    location = job.get('location', {}).get('display_name', region)
                    is_remote = 'remote' in location.lower() or 'remote' in title.lower()

                    salary_min = job.get('salary_min', '')
                    salary_max = job.get('salary_max', '')
                    salary = f"{salary_min}" + (f" – {salary_max}" if salary_max else '')

                    jobs.append({
                        'id':              generate_id('adzuna', str(job.get('id', ''))),
                        'title':           title,
                        'company':         job.get('company', {}).get('display_name', 'Unknown'),
                        'location':        location,
                        'region':          region,
                        'level':           detect_level(title, desc),
                        'job_type':        job.get('contract_type', 'full_time'),
                        'description':     desc,
                        'apply_url':       job.get('redirect_url', ''),
                        'source':          'Adzuna',
                        'posted_date':     posted.isoformat() if posted else datetime.now(timezone.utc).isoformat(),
                        'is_remote':       is_remote,
                        'nigeria_friendly': detect_nigeria_friendly(location, desc) if is_remote else False,
                        'tags':            [],
                        'salary':          salary.strip(' –'),
                    })
                time.sleep(1.0)
            except Exception as e:
                print(f"  [Adzuna {code}] {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# SOURCE 5 · JSearch via RapidAPI  (free tier — LinkedIn / Indeed / Glassdoor)
# ════════════════════════════════════════════════════════════════════════════

def fetch_jsearch(days_back: int = 7) -> list:
    """Aggregate LinkedIn, Indeed, Glassdoor via JSearch RapidAPI (200 free calls/mo)."""
    cfg     = load_config()
    api_key = cfg.get('api_keys', {}).get('jsearch_rapidapi_key', '')
    if not api_key:
        print("  [JSearch] Key not set in config.json — skipping.")
        return []

    jobs    = []
    headers = {
        'X-RapidAPI-Key':  api_key,
        'X-RapidAPI-Host': 'jsearch.p.rapidapi.com',
    }
    if days_back <= 1:
        date_posted = 'today'
    elif days_back <= 3:
        date_posted = '3days'
    else:
        date_posted = 'week'

    queries = [
        'data scientist remote',
        'machine learning engineer remote',
        'junior data scientist',
        'senior data scientist europe',
        'data scientist canada',
    ]

    for query in queries:
        try:
            r = requests.get(
                'https://jsearch.p.rapidapi.com/search',
                headers=headers,
                params={
                    'query':       query,
                    'page':        '1',
                    'num_pages':   '3',
                    'date_posted': date_posted,
                },
                timeout=30,
            )
            r.raise_for_status()

            for job in r.json().get('data', []):
                title = job.get('job_title', '')
                desc  = clean_description(job.get('job_description', ''))
                if not is_data_science_role(title, desc):
                    continue

                loc_parts = [job.get('job_city',''), job.get('job_state',''), job.get('job_country','')]
                location  = ', '.join(p for p in loc_parts if p)
                is_remote = bool(job.get('job_is_remote', False))

                posted = parse_date(job.get('job_posted_at_datetime_utc', ''))
                if posted and not is_within_days(posted, days_back):
                    continue

                publisher = job.get('job_publisher', 'LinkedIn/Indeed')
                jobs.append({
                    'id':              generate_id('jsearch', job.get('job_id', title[:30])),
                    'title':           title,
                    'company':         job.get('employer_name', 'Unknown'),
                    'location':        location or ('Remote' if is_remote else 'Unknown'),
                    'region':          'Remote' if is_remote else detect_region(location),
                    'level':           detect_level(title, desc),
                    'job_type':        job.get('job_employment_type', 'FULLTIME').lower(),
                    'description':     desc,
                    'apply_url':       job.get('job_apply_link', ''),
                    'source':          publisher,
                    'posted_date':     posted.isoformat() if posted else datetime.now(timezone.utc).isoformat(),
                    'is_remote':       is_remote,
                    'nigeria_friendly': detect_nigeria_friendly('worldwide' if is_remote else location, desc),
                    'tags':            job.get('job_required_skills') or [],
                    'salary':          '',
                })
            time.sleep(1.5)
        except Exception as e:
            print(f"  [JSearch '{query}'] {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# SOURCE 6 · Reed.co.uk  (free key — UK jobs)
# ════════════════════════════════════════════════════════════════════════════

def fetch_reed(days_back: int = 7) -> list:
    """UK data science jobs from Reed.co.uk API."""
    cfg     = load_config()
    api_key = cfg.get('api_keys', {}).get('reed_api_key', '')
    if not api_key:
        print("  [Reed] Key not set in config.json — skipping.")
        return []

    jobs = []
    for query in ['data scientist', 'machine learning engineer', 'AI engineer']:
        try:
            r = requests.get(
                'https://www.reed.co.uk/api/1.0/search',
                auth=(api_key, ''),
                params={'keywords': query, 'daysAgeMax': days_back, 'resultsToTake': 50},
                timeout=30,
            )
            r.raise_for_status()

            for job in r.json().get('results', []):
                title = job.get('jobTitle', '')
                desc  = clean_description(job.get('jobDescription', ''))
                if not is_data_science_role(title, desc):
                    continue

                posted    = parse_date(job.get('date', ''))
                location  = job.get('locationName', 'UK')
                is_remote = 'remote' in location.lower()

                sal_min = job.get('minimumSalary', '')
                sal_max = job.get('maximumSalary', '')
                salary  = f"{sal_min}" + (f" – {sal_max}" if sal_max else '')

                jobs.append({
                    'id':              generate_id('reed', str(job.get('jobId', ''))),
                    'title':           title,
                    'company':         job.get('employerName', 'Unknown'),
                    'location':        location,
                    'region':          'UK',
                    'level':           detect_level(title, desc),
                    'job_type':        'full_time',
                    'description':     desc,
                    'apply_url':       job.get('jobUrl', ''),
                    'source':          'Reed',
                    'posted_date':     posted.isoformat() if posted else datetime.now(timezone.utc).isoformat(),
                    'is_remote':       is_remote,
                    'nigeria_friendly': detect_nigeria_friendly(location, desc),
                    'tags':            [],
                    'salary':          salary.strip(' –'),
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [Reed] {e}")
    return jobs


# ════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════

def fetch_all_jobs(days_back: int = 7) -> tuple:
    """
    Run all fetchers, deduplicate, return (jobs_list, results_summary).
    Priority order: USA → Europe → Canada → UK → Worldwide → Remote → Other.
    """
    REGION_PRIORITY = {'USA': 0, 'Europe': 1, 'Canada': 2, 'UK': 3,
                       'Worldwide': 4, 'Remote': 5, 'Other': 6}

    all_jobs: list = []
    results:  dict = {}

    sources = [
        ('Remotive',       fetch_remotive),
        ('Arbeitnow',      fetch_arbeitnow),
        ('WeWorkRemotely', fetch_weworkremotely),
        ('Adzuna',         fetch_adzuna),
        ('JSearch',        fetch_jsearch),
        ('Reed',           fetch_reed),
    ]

    for name, fn in sources:
        print(f"  -> {name}...", end=' ', flush=True)
        try:
            batch = fn(days_back)
            results[name] = len(batch)
            all_jobs.extend(batch)
            print(f"{len(batch)} jobs")
        except Exception as e:
            results[name] = 0
            print(f"ERROR — {e}")

    # Deduplicate on (title[:40] + company[:25] + region) to avoid dropping
    # legitimate roles at different locations while still catching true duplicates
    # across sources (e.g. same job posted on LinkedIn and Indeed via JSearch).
    seen: set   = set()
    unique: list = []
    for job in all_jobs:
        key = (
            f"{job['title'].lower()[:40]}_"
            f"{job.get('company','').lower()[:25]}_"
            f"{job.get('region','').lower()}"
        )
        if key not in seen:
            seen.add(key)
            unique.append(job)

    # Two-pass stable sort: newest date first within each priority group.
    # Pass 1 — date descending (stable sort preserves this order in pass 2).
    unique.sort(key=lambda j: j.get('posted_date', ''), reverse=True)
    # Pass 2 — nigeria-friendly first, then by region priority (stable, so date
    # order is preserved within each group).
    unique.sort(key=lambda j: (
        0 if j.get('nigeria_friendly') else 1,
        REGION_PRIORITY.get(j.get('region', 'Other'), 7),
    ))

    print(f"\n  [done] {len(unique)} unique jobs (raw: {len(all_jobs)})")
    return unique, results
