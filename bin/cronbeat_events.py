#!/usr/bin/env python3
"""Emit one JSON event per cycle with systemd timer and cron heartbeat summary."""
import sys

from cronbeat_common import discover, emit, fail


def main():
    try:
        data = discover()
    except Exception as exc:
        fail("events discovery degraded: %s" % exc)
        data = {"status": "absent", "timers_total": 0, "timers_stale": 0,
                "stale_timers": [], "cron_jobs": 0}
    emit(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
