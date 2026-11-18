"""Shared collection logic for TA-cronbeat scripted inputs (systemd timers + cron)."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

LIST_TIMERS_CMD = ["systemctl", "list-timers", "--all", "--no-legend", "--no-pager", "--plain"]
CRONTAB_PATH = "/etc/crontab"
CRON_D = "/etc/cron.d"

TIMER_STALE_HOURS = 24.0

DATE_TOKEN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_TOKEN = re.compile(r"^\d{2}:\d{2}:\d{2}$")
TIMER_TS = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})")
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")
TIME_FIELD = re.compile(r"^[\d*,/\-]+$")


def run_cmd(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=25,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _read_lines(path):
    try:
        with open(path) as fh:
            return fh.readlines()
    except OSError:
        return []


def _timer_dt(s):
    m = TIMER_TS.match(s or "")
    if not m:
        return None
    try:
        return datetime(*[int(g) for g in m.groups()])
    except ValueError:
        return None


def _timer_row(parts):
    if len(parts) < 4:
        return None
    stamps = []
    for j in range(len(parts) - 1):
        if DATE_TOKEN.match(parts[j]) and TIME_TOKEN.match(parts[j + 1]):
            stamps.append(j)
            if len(stamps) == 2:
                break
    nxt = parts[stamps[0]] + " " + parts[stamps[0] + 1] if stamps else None
    last = parts[stamps[1]] + " " + parts[stamps[1] + 1] if len(stamps) > 1 else None
    return nxt, last, parts[-2]


def _list_timers():
    p = run_cmd(LIST_TIMERS_CMD)
    if p is None or p.returncode != 0 or not (p.stdout or "").strip():
        return None
    return p.stdout


def collect_timers():
    text = _list_timers()
    if text is None:
        return None
    now = datetime.now()
    stale_after = timedelta(hours=TIMER_STALE_HOURS)
    total = 0
    stale = []
    for line in text.splitlines():
        row = _timer_row(line.split())
        if row is None:
            continue
        nxt, last, unit = row
        if not unit.endswith(".timer"):
            continue
        total += 1
        last_dt = _timer_dt(last)
        next_dt = _timer_dt(nxt)
        if last_dt is not None and next_dt is not None and now - last_dt > stale_after and next_dt < now:
            stale.append(unit)
    return {"timers_total": total, "timers_stale": len(stale), "stale_timers": sorted(stale)}


def _count_cron_file(path):
    count = 0
    for line in _read_lines(path):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ENV_ASSIGN.match(stripped):
            continue
        parts = stripped.split()
        if len(parts) < 6:
            continue
        if all(TIME_FIELD.match(t) for t in parts[:5]):
            count += 1
    return count


def count_cron_jobs():
    total = _count_cron_file(CRONTAB_PATH)
    try:
        names = sorted(os.listdir(CRON_D))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(CRON_D, name)
        if os.path.isfile(path):
            total += _count_cron_file(path)
    return total


def discover():
    timers = collect_timers()
    if timers is None:
        return {"status": "absent", "timers_total": 0, "timers_stale": 0,
                "stale_timers": [], "cron_jobs": 0}
    status = "alarm" if timers["timers_stale"] > 0 else "ok"
    return {
        "status": status,
        "timers_total": timers["timers_total"],
        "timers_stale": timers["timers_stale"],
        "stale_timers": timers["stale_timers"],
        "cron_jobs": count_cron_jobs(),
    }


def metrics_payload(data):
    if data.get("status") == "absent":
        return {}
    payload = {
        "timers_total": data.get("timers_total"),
        "timers_stale": data.get("timers_stale"),
        "cron_jobs": data.get("cron_jobs"),
    }
    return {k: int(v) for k, v in payload.items() if v is not None}


def emit(payload):
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()


def fail(message):
    sys.stderr.write("TA-cronbeat collection error: %s\n" % message)
    return 1
