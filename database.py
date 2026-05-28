"""
database.py — SQLite storage layer for DS Job Bot.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and indexes if they don't exist."""
    conn = get_conn()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            company         TEXT,
            location        TEXT,
            region          TEXT,
            level           TEXT,
            job_type        TEXT,
            description     TEXT,
            apply_url       TEXT,
            source          TEXT,
            posted_date     TEXT,
            fetched_date    TEXT,
            is_remote       INTEGER DEFAULT 0,
            nigeria_friendly INTEGER DEFAULT 0,
            tags            TEXT,
            salary          TEXT
        );

        CREATE TABLE IF NOT EXISTS fetch_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fetch_date  TEXT,
            source      TEXT,
            jobs_found  INTEGER,
            status      TEXT,
            error       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_posted    ON jobs(posted_date);
        CREATE INDEX IF NOT EXISTS idx_region    ON jobs(region);
        CREATE INDEX IF NOT EXISTS idx_level     ON jobs(level);
        CREATE INDEX IF NOT EXISTS idx_nigeria   ON jobs(nigeria_friendly);
        CREATE INDEX IF NOT EXISTS idx_source    ON jobs(source);
    ''')
    conn.commit()
    conn.close()


def upsert_jobs(jobs: list):
    """Bulk insert/replace a list of job dicts."""
    if not jobs:
        return
    conn = get_conn()
    try:
        c = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        for job in jobs:
            try:
                c.execute('''
                    INSERT OR REPLACE INTO jobs
                      (id, title, company, location, region, level, job_type,
                       description, apply_url, source, posted_date, fetched_date,
                       is_remote, nigeria_friendly, tags, salary)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    job['id'],
                    job.get('title', ''),
                    job.get('company', 'Unknown'),
                    job.get('location', 'Remote'),
                    job.get('region', 'Remote'),
                    job.get('level', 'Mid'),
                    job.get('job_type', ''),
                    job.get('description', ''),
                    job.get('apply_url', ''),
                    job.get('source', ''),
                    job.get('posted_date', now),
                    now,
                    1 if job.get('is_remote') else 0,
                    1 if job.get('nigeria_friendly') else 0,
                    json.dumps(job.get('tags', [])),
                    job.get('salary', ''),
                ))
            except Exception as e:
                print(f"  [DB] Error inserting {job.get('id')}: {e}")
        conn.commit()
    finally:
        conn.close()


def log_fetch(source: str, jobs_found: int, status: str, error: str = ''):
    conn = get_conn()
    try:
        conn.execute(
            'INSERT INTO fetch_log (fetch_date, source, jobs_found, status, error) VALUES (?,?,?,?,?)',
            (datetime.now(timezone.utc).isoformat(), source, jobs_found, status, error)
        )
        conn.commit()
    finally:
        conn.close()


def get_jobs(filters: dict = None) -> list:
    """Return jobs matching optional filters."""
    conn = get_conn()
    try:
        c = conn.cursor()

        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if filters:
            if filters.get('level') and filters['level'] != 'All':
                query += " AND level = ?"
                params.append(filters['level'])
            if filters.get('region') and filters['region'] != 'All':
                query += " AND region = ?"
                params.append(filters['region'])
            if filters.get('source') and filters['source'] != 'All':
                query += " AND source = ?"
                params.append(filters['source'])
            if filters.get('remote_only'):
                query += " AND is_remote = 1"
            if filters.get('nigeria_friendly'):
                query += " AND nigeria_friendly = 1"
            if filters.get('search'):
                s = f"%{filters['search']}%"
                query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
                params.extend([s, s, s])

        query += " ORDER BY nigeria_friendly DESC, posted_date DESC LIMIT 1000"
        c.execute(query, params)
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    """Return aggregate statistics for the dashboard header."""
    conn = get_conn()
    try:
        c = conn.cursor()

        def scalar(sql, params=()):
            c.execute(sql, params)
            row = c.fetchone()
            return row[0] if row else 0

        return {
            'total':            scalar("SELECT COUNT(*) FROM jobs"),
            'nigeria_friendly': scalar("SELECT COUNT(*) FROM jobs WHERE nigeria_friendly=1"),
            'remote':           scalar("SELECT COUNT(*) FROM jobs WHERE is_remote=1"),
            'by_level':  dict(c.execute("SELECT level, COUNT(*) FROM jobs GROUP BY level").fetchall()),
            'by_region': dict(c.execute("SELECT region, COUNT(*) FROM jobs GROUP BY region ORDER BY 2 DESC").fetchall()),
            'by_source': dict(c.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY 2 DESC").fetchall()),
        }
    finally:
        conn.close()


def get_last_fetch() -> str:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT MAX(fetched_date) FROM jobs")
        row = c.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def purge_old_jobs(days: int = 14):
    """Remove jobs not seen in a fetch within the last `days` days.

    Uses fetched_date (when we last saw the job) rather than posted_date so
    that legitimately older postings are not deleted while they remain active.
    """
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM jobs WHERE julianday('now') - julianday(fetched_date) > ?",
            (days,)
        )
        conn.commit()
    finally:
        conn.close()
