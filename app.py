"""
app.py — Flask web server + background scheduler for DS Job Bot.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import schedule
import time

from flask import Flask, jsonify, render_template, request

import database
from fetchers import fetch_all_jobs

app = Flask(__name__)

# ── Shared state ─────────────────────────────────────────────────────────────
_fetch_state = {
    'running':      False,
    'last_run':     None,
    'last_results': {},
    'error':        None,
}
_fetch_lock = threading.Lock()


def load_config() -> dict:
    path = Path(__file__).parent / 'config.json'
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print("[Config] config.json not found — using defaults.")
        return {'settings': {'days_back': 7, 'auto_fetch_on_start': True}}
    except json.JSONDecodeError as e:
        print(f"[Config] config.json is malformed ({e}) — using defaults. API keys will not load.")
        return {'settings': {'days_back': 7, 'auto_fetch_on_start': True}}
    except Exception as e:
        print(f"[Config] Could not read config.json ({e}) — using defaults.")
        return {'settings': {'days_back': 7, 'auto_fetch_on_start': True}}


def _do_fetch():
    """Fetch jobs and store them. Called from background threads."""
    with _fetch_lock:
        if _fetch_state['running']:
            return
        _fetch_state['running'] = True
        _fetch_state['error']   = None
    try:
        cfg       = load_config()
        settings  = cfg.get('settings', {})
        days_back = settings.get('days_back', 7)
        purge_days = settings.get('purge_older_than_days', 14)
        print(f"\n[{datetime.now(timezone.utc).isoformat()}] Fetching jobs (last {days_back} days)...")
        jobs, results = fetch_all_jobs(days_back)
        database.upsert_jobs(jobs)
        database.purge_old_jobs(days=purge_days)
        for source, count in results.items():
            database.log_fetch(source, count, 'success')
        with _fetch_lock:
            _fetch_state['last_results'] = results
            _fetch_state['last_run']     = datetime.now(timezone.utc).isoformat()
        print(f"[Fetch complete] {sum(results.values())} total, {len(jobs)} unique stored.")
    except Exception as e:
        with _fetch_lock:
            _fetch_state['error'] = str(e)
        print(f"[Fetch ERROR] {e}")
    finally:
        with _fetch_lock:
            _fetch_state['running'] = False


def _background_fetch():
    thread = threading.Thread(target=_do_fetch, daemon=True)
    thread.start()


def _run_scheduler():
    """Runs in a daemon thread; fires daily fetch at the configured UTC time."""
    cfg = load_config()
    fetch_time = cfg.get('settings', {}).get('daily_fetch_time_utc', '06:00')
    schedule.every().day.at(fetch_time).do(_background_fetch)
    print(f"[Scheduler] Daily fetch scheduled at {fetch_time} UTC.")
    while True:
        schedule.run_pending()
        time.sleep(30)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/jobs')
def api_jobs():
    filters = {
        'level':           request.args.get('level', 'All'),
        'region':          request.args.get('region', 'All'),
        'source':          request.args.get('source', 'All'),
        'remote_only':     request.args.get('remote_only') == 'true',
        'nigeria_friendly': request.args.get('nigeria_friendly') == 'true',
        'search':          request.args.get('search', ''),
    }
    jobs = database.get_jobs(filters)
    return jsonify({'jobs': jobs, 'total': len(jobs)})


@app.route('/api/stats')
def api_stats():
    stats = database.get_stats()
    stats['fetch'] = {
        'running':  _fetch_state['running'],
        'last_run': _fetch_state['last_run'],
        'results':  _fetch_state['last_results'],
        'error':    _fetch_state['error'],
    }
    stats['last_fetch'] = database.get_last_fetch()
    return jsonify(stats)


@app.route('/api/fetch', methods=['POST'])
def api_fetch():
    with _fetch_lock:
        if _fetch_state['running']:
            return jsonify({'status': 'already_running'}), 409
    _background_fetch()
    return jsonify({'status': 'started'})


@app.route('/api/fetch/status')
def api_fetch_status():
    return jsonify(_fetch_state)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    database.init_db()

    cfg = load_config()

    # Start daily scheduler
    sched_thread = threading.Thread(target=_run_scheduler, daemon=True)
    sched_thread.start()

    # Optional auto-fetch on start
    if cfg.get('settings', {}).get('auto_fetch_on_start', True):
        _background_fetch()

    print("\n" + "=" * 60)
    print("  DS Job Bot Dashboard")
    print("  http://localhost:5000")
    print("  Auto-fetches daily at 06:00 UTC")
    print("=" * 60 + "\n")

    app.run(debug=False, port=5000, host='0.0.0.0', threaded=True)
