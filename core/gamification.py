"""Shared gamification rules: XP awards, levels and streaks.

XP is cumulative (it never resets) and the level is derived from it, so
leaderboards can rank directly on Student.xp_points.
"""
from datetime import timedelta

from django.utils import timezone

XP_PER_LEVEL = 500
XP_PER_CORRECT = 10
XP_PER_TEST = 10
XP_DAILY_FIRST_TEST = 5
XP_PERFECT_SCORE = 20
XP_STREAK_BONUS = 50
STREAK_BONUS_DAYS = 7


def level_for_xp(xp):
    return xp // XP_PER_LEVEL + 1


def next_level_xp(level):
    """Cumulative XP needed to reach the level after `level`."""
    return level * XP_PER_LEVEL


def compute_streak(dates, today=None):
    """Consecutive practice days ending today or yesterday.

    A streak whose most recent day is older than yesterday is broken (0).
    """
    today = today or timezone.localdate()
    days = set(dates)
    if today in days:
        day = today
    elif today - timedelta(days=1) in days:
        day = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def user_streak(user, today=None):
    from .models import TestResult
    dates = (
        TestResult.objects.filter(student=user)
        .values_list('created_at__date', flat=True)
        .distinct()
    )
    return compute_streak(dates, today)
