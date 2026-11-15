#!/usr/bin/env python3
"""Emit one JSON event per cycle with systemd timer and cron heartbeat summary."""
import sys

from cronbeat_common import discover, emit


def main():
    emit(discover())
    return 0


if __name__ == "__main__":
    sys.exit(main())
