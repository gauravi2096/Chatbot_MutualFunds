"""
Phase 4 — Scheduler and daily update configuration.
"""

from pathlib import Path

# Project root (parent of phase_4)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default schedule (for local/cron documentation; GitHub Actions uses its own schedule)
DEFAULT_UPDATE_HOUR_UTC = 4
DEFAULT_UPDATE_MINUTE_UTC = 30  # 10:00 AM IST = 04:30 UTC
