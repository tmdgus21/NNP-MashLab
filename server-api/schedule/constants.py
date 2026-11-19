"""Coordination constants (coordination-algorithm.md)."""
from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")

SLOT_MINUTES = 30
MIN_CANDIDATE_MINUTES = 60
MIN_PEOPLE = 2
INPUT_WINDOW = timedelta(hours=24)
ALL_DONE_GRACE = timedelta(minutes=3)
MAX_EXTENSIONS = 1
EXTENSION = timedelta(hours=24)
VOTING_DURATION = timedelta(hours=6)
VOTE_LEAD = timedelta(minutes=30)
MIN_VOTING = timedelta(hours=1)
MAX_READJUSTS = 4  # cycles 1..4 after initial cycle 0
MAX_HINTS = 5
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
