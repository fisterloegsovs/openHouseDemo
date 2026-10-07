#!/usr/bin/env python3
"""Kompatibel genvej til red_team.py. Blue team startes separat."""

from red_team import Scene, load_records, main, render


if __name__ == "__main__":
    raise SystemExit(main())
