from app.world.clock import (
    TICKS_PER_DAY,
    day_of_tick,
    first_tick_of_day,
    tick_bounds_for_days,
    world_clock,
)


def test_day_one_starts_at_0800():
    assert world_clock(0) == {"day": 1, "time": "08:00", "phase": "morning"}


def test_ticks_per_day():
    assert TICKS_PER_DAY == 72


def test_day_boundaries_are_consistent():
    # every tick's day matches first_tick_of_day's inverse
    for day in range(1, 6):
        start = first_tick_of_day(day)
        assert day_of_tick(start) == day
        if day > 1:
            assert day_of_tick(start - 1) == day - 1


def test_day_two_starts_at_midnight():
    start = first_tick_of_day(2)
    assert world_clock(start)["time"] == "00:00"
    assert world_clock(start)["day"] == 2


def test_tick_bounds_cover_range_exactly():
    lo, hi = tick_bounds_for_days(3, 7)
    assert day_of_tick(lo) == 3
    assert day_of_tick(hi) == 7
    assert day_of_tick(lo - 1) == 2
    assert day_of_tick(hi + 1) == 8


def test_single_day_bounds():
    lo, hi = tick_bounds_for_days(1, 1)
    assert lo == 0
    assert day_of_tick(hi) == 1
    assert day_of_tick(hi + 1) == 2


def test_phases():
    assert world_clock(0)["phase"] == "morning"     # 08:00
    assert world_clock(15)["phase"] == "afternoon"  # 13:00
    assert world_clock(33)["phase"] == "evening"    # 19:00
    assert world_clock(45)["phase"] == "night"      # 23:00


def test_next_wake_tick_is_always_0600_and_in_future():
    from app.world.clock import next_wake_tick

    for tick in [0, 10, 47, 48, 60, 66, 100, 130, 200]:
        wake = next_wake_tick(tick)
        assert wake > tick
        assert world_clock(wake)["time"] == "06:00"


def test_sleep_at_night_wakes_same_morning():
    from app.world.clock import next_wake_tick

    # tick 50 is day 2, 00:40 -> wake at day 2, 06:00
    assert world_clock(50) == {"day": 2, "time": "00:40", "phase": "night"}
    wake = next_wake_tick(50)
    assert world_clock(wake) == {"day": 2, "time": "06:00", "phase": "morning"}
