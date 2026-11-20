"""Weekday timetables and activity rules.

Five cohorts (UG years 1-4 and postgraduate) follow a Monday-Friday timetable.
Each class slot is (start hour, duration in hours, building). Outside classes,
agents choose meals, library, sports and market visits with the propensities
below. Times are on a 15-minute grid between 06:00 and 24:00.
"""

from __future__ import annotations

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
COHORTS = ("UG1", "UG2", "UG3", "UG4", "PG")
COHORT_SHARE = {"UG1": 0.22, "UG2": 0.21, "UG3": 0.20, "UG4": 0.19, "PG": 0.18}

DAY_START_H = 6.0
DAY_END_H = 24.0
STEP_H = 0.25
N_STEPS = int((DAY_END_H - DAY_START_H) / STEP_H)  # 72

ACTIVITIES = ("home", "class", "study", "meal", "library", "sports", "market", "health", "travel")

A, B, C, D, M, L = ("Academic Block A", "Academic Block B", "Academic Block C",
                    "Academic Block D", "Main Building", "Central Library")

TIMETABLE = {
    "UG1": {
        "Mon": [(8, 2, M), (10, 1, A), (14, 3, C)],
        "Tue": [(8, 1, A), (9, 2, M), (11, 1, B), (14, 2, C)],
        "Wed": [(8, 2, M), (10, 2, A), (15, 2, B)],
        "Thu": [(9, 2, M), (11, 1, A), (14, 3, C)],
        "Fri": [(8, 1, A), (9, 2, M), (14, 2, B)],
    },
    "UG2": {
        "Mon": [(9, 2, B), (11, 1, M), (14, 3, D)],
        "Tue": [(8, 2, B), (10, 2, D), (15, 2, A)],
        "Wed": [(9, 2, B), (11, 1, M), (14, 3, D)],
        "Thu": [(8, 2, D), (10, 1, B), (14, 2, A)],
        "Fri": [(9, 2, B), (11, 1, M), (15, 2, D)],
    },
    "UG3": {
        "Mon": [(8, 2, C), (10, 2, A), (14, 2, A)],
        "Tue": [(10, 2, C), (14, 3, A)],
        "Wed": [(8, 2, A), (11, 1, C), (14, 3, C)],
        "Thu": [(10, 2, A), (15, 2, C)],
        "Fri": [(8, 2, C), (10, 1, A), (14, 3, A)],
    },
    "UG4": {
        "Mon": [(10, 2, D), (15, 2, B)],
        "Tue": [(8, 2, D), (14, 2, B)],
        "Wed": [(10, 2, B), (14, 3, D)],
        "Thu": [(8, 2, B), (10, 2, D)],
        "Fri": [(11, 1, D), (14, 3, B)],
    },
    "PG": {
        "Mon": [(9, 3, M), (14, 2, L)],
        "Tue": [(10, 2, M)],
        "Wed": [(9, 2, M), (14, 2, M)],
        "Thu": [(11, 1, M), (15, 2, L)],
        "Fri": [(9, 3, M)],
    },
}

# Probabilities applied per agent and day.
ATTENDANCE = 0.88
LIBRARY_GAP = 0.35          # use a free gap of 2 h or more in the library instead of going home
SPORTS_EVENING = 0.30       # 17:30-19:00 at the sports complex or central lawn
LIBRARY_NIGHT = {"UG1": 0.15, "UG2": 0.18, "UG3": 0.22, "UG4": 0.25, "PG": 0.40}
MARKET_NIGHT = 0.20         # 21:00-22:00 at the market or dining centre
HEALTH_VISIT = 0.006        # 45-minute visit to the health centre between 09:00 and 17:00
# Meals in the home hall mess: (earliest start, latest start, duration in hours).
MEALS = ((7.25, 8.25, 0.5), (12.75, 13.75, 0.5), (19.75, 21.0, 0.75))

WALK_SPEED_MS = 1.3
CYCLE_SPEED_MS = 4.0
CYCLE_SHARE = 0.65


def step_of(hour: float) -> int:
    return int(round((hour - DAY_START_H) / STEP_H))


def hour_of(step: int) -> float:
    return DAY_START_H + step * STEP_H


def clock(step: int) -> str:
    h = hour_of(step)
    return f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"
