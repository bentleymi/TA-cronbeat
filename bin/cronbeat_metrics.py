#!/usr/bin/env python3
"""Emit flat numeric metrics (one JSON event per cycle) for analytics."""
import sys

from cronbeat_common import discover, emit, fail, metrics_payload


def main():
    try:
        data = discover()
    except Exception as exc:
        fail("metrics discovery degraded: %s" % exc)
        data = {"timers_total": 0, "timers_stale": 0, "cron_jobs": 0}
    emit(metrics_payload(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
