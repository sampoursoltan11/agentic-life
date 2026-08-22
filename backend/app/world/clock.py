"""The in-world clock: one tick = 20 minutes, day 1 starts at 08:00.

Single source of truth for day math - the simulation (perception), the
extraction API, and the frontend HUD (which mirrors these constants in
App.tsx) must all agree.
"""

MINUTES_PER_TICK = 20
DAY_START_MIN = 8 * 60
TICKS_PER_DAY = 24 * 60 // MINUTES_PER_TICK  # 72


def world_clock(tick: int) -> dict:
    total = DAY_START_MIN + tick * MINUTES_PER_TICK
    day = total // (24 * 60) + 1
    hh, mm = (total % (24 * 60)) // 60, total % 60
    if 6 <= hh < 12:
        phase = "morning"
    elif 12 <= hh < 18:
        phase = "afternoon"
    elif 18 <= hh < 22:
        phase = "evening"
    else:
        phase = "night"
    return {"day": day, "time": f"{hh:02d}:{mm:02d}", "phase": phase}


def day_of_tick(tick: int) -> int:
    return (DAY_START_MIN + tick * MINUTES_PER_TICK) // (24 * 60) + 1


def first_tick_of_day(day: int) -> int:
    """The first tick that falls on the given day (day 1 starts at tick 0)."""
    if day <= 1:
        return 0
    # smallest tick with DAY_START_MIN + tick*MPT >= (day-1)*1440
    minutes_needed = (day - 1) * 24 * 60 - DAY_START_MIN
    return -(-minutes_needed // MINUTES_PER_TICK)  # ceil division


def tick_bounds_for_days(day_from: int, day_to: int) -> tuple[int, int]:
    """Inclusive tick range covering [day_from, day_to]."""
    return first_tick_of_day(day_from), first_tick_of_day(day_to + 1) - 1


WAKE_HOUR = 6


def next_wake_tick(tick: int) -> int:
    """The tick a citizen falling asleep now sleeps until: the next 06:00."""
    day = day_of_tick(tick)
    ticks_to_six = WAKE_HOUR * 60 // MINUTES_PER_TICK  # 06:00 is 18 ticks after midnight
    same_day_six = first_tick_of_day(day) + (ticks_to_six if day > 1 else 0)
    # day 1 starts at 08:00, so its "06:00" never exists; day>1 starts at 00:00
    if day > 1 and tick < same_day_six:
        return same_day_six
    return first_tick_of_day(day + 1) + ticks_to_six
