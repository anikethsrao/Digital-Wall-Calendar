from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from wallcal import calendars, hub, render, weather
from wallcal.config import PALETTE, CalendarSource, Config

TZ = ZoneInfo("America/Toronto")
SRC = CalendarSource("Test", "unused", "blue")


def ics(*events: str) -> str:
    body = "\n".join(f"BEGIN:VEVENT\nUID:{i}\n{e}\nEND:VEVENT" for i, e in enumerate(events))
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\n{body}\nEND:VCALENDAR\n"


def days(text, first, last):
    return calendars.by_day(calendars.parse(text, SRC, first, last, TZ))


def test_weekly_repeat_skips_the_cancelled_week():
    text = ics("DTSTART;TZID=America/Toronto:20261101T180000\n"
               "DTEND;TZID=America/Toronto:20261101T190000\n"
               "RRULE:FREQ=WEEKLY;BYDAY=SU\n"
               "EXDATE;TZID=America/Toronto:20261115T180000\nSUMMARY:Dinner")
    got = days(text, date(2026, 11, 1), date(2026, 11, 30))
    assert sorted(got) == [date(2026, 11, d) for d in (1, 8, 22, 29)]


def test_all_day_event_stays_on_its_own_day():
    got = days(ics("DTSTART;VALUE=DATE:20261111\nSUMMARY:Holiday"),
               date(2026, 11, 1), date(2026, 11, 30))
    assert list(got) == [date(2026, 11, 11)]
    assert got[date(2026, 11, 11)][0].all_day


def test_multi_day_all_day_event_excludes_its_end_date():
    got = days(ics("DTSTART;VALUE=DATE:20261126\nDTEND;VALUE=DATE:20261130\nSUMMARY:Visit"),
               date(2026, 11, 1), date(2026, 11, 30))
    assert sorted(got) == [date(2026, 11, d) for d in (26, 27, 28, 29)]


def test_event_in_another_time_zone_shows_in_local_time():
    got = days(ics("DTSTART;TZID=America/Los_Angeles:20261112T110000\n"
                   "DTEND;TZID=America/Los_Angeles:20261112T120000\nSUMMARY:Call"),
               date(2026, 11, 1), date(2026, 11, 30))
    ev = got[date(2026, 11, 12)][0]
    assert (ev.start.hour, ev.start.minute) == (14, 0)


def test_late_night_utc_event_lands_on_the_local_day():
    # 02:00 UTC on the 13th is 9 PM on the 12th in Toronto.
    got = days(ics("DTSTART:20261113T020000Z\nDTEND:20261113T030000Z\nSUMMARY:Late"),
               date(2026, 11, 1), date(2026, 11, 30))
    assert list(got) == [date(2026, 11, 12)]


def test_repeat_keeps_its_clock_time_across_daylight_saving():
    # Clocks go back on Nov 1, 2026. A 9 AM weekly event stays at 9 AM.
    text = ics("DTSTART;TZID=America/Toronto:20261026T090000\n"
               "DTEND;TZID=America/Toronto:20261026T093000\n"
               "RRULE:FREQ=WEEKLY;COUNT=3\nSUMMARY:Standup")
    got = days(text, date(2026, 10, 25), date(2026, 11, 14))
    assert [e[0].start.hour for e in got.values()] == [9, 9, 9]
    assert sorted(got) == [date(2026, 10, 26), date(2026, 11, 2), date(2026, 11, 9)]


def test_event_ending_at_midnight_does_not_spill_into_the_next_day():
    got = days(ics("DTSTART;TZID=America/Toronto:20261121T190000\n"
                   "DTEND;TZID=America/Toronto:20261122T000000\nSUMMARY:Movie"),
               date(2026, 11, 1), date(2026, 11, 30))
    assert list(got) == [date(2026, 11, 21)]


def test_event_crossing_midnight_shows_on_both_days():
    got = days(ics("DTSTART;TZID=America/Toronto:20261121T220000\n"
                   "DTEND;TZID=America/Toronto:20261122T010000\nSUMMARY:Party"),
               date(2026, 11, 1), date(2026, 11, 30))
    assert sorted(got) == [date(2026, 11, 21), date(2026, 11, 22)]


def test_cancelled_events_are_hidden():
    got = days(ics("DTSTART;VALUE=DATE:20261111\nSTATUS:CANCELLED\nSUMMARY:Off"),
               date(2026, 11, 1), date(2026, 11, 30))
    assert got == {}


def test_all_day_events_sort_before_timed_ones():
    text = ics("DTSTART;TZID=America/Toronto:20261111T080000\n"
               "DTEND;TZID=America/Toronto:20261111T090000\nSUMMARY:Early",
               "DTSTART;VALUE=DATE:20261111\nSUMMARY:Holiday")
    got = days(text, date(2026, 11, 1), date(2026, 11, 30))
    assert [e.title for e in got[date(2026, 11, 11)]] == ["Holiday", "Early"]


def test_month_grid_starts_on_sunday_and_covers_the_month():
    weeks = render.month_grid(date(2026, 11, 11), 6)
    assert all(w[0].weekday() == 6 for w in weeks)
    assert weeks[0][0] == date(2026, 11, 1) and weeks[-1][-1] == date(2026, 12, 5)


def test_clock_formats():
    assert render.clock(datetime(2026, 1, 1, 9, 0), 12) == "9a"
    assert render.clock(datetime(2026, 1, 1, 14, 30), 12) == "2:30p"
    assert render.clock(datetime(2026, 1, 1, 0, 5), 12) == "12:05a"
    assert render.clock(datetime(2026, 1, 1, 14, 30), 24) == "14:30"


def _sample_cfg(tmp_path) -> Config:
    samples = Path(__file__).parent.parent / "samples"
    return Config(
        timezone=TZ, week_start=6,
        calendars=[CalendarSource("Family", "family.ics", "blue"),
                   CalendarSource("Work", "work.ics", "red"),
                   CalendarSource("School", "school.ics", "green")],
        data_dir=tmp_path / "data", base_dir=samples,
    )


def test_panel_image_is_the_right_size_and_only_six_colours(tmp_path):
    cfg = _sample_cfg(tmp_path)
    forecast = weather.load_file(cfg.base_dir / "weather.json")
    now = datetime(2026, 11, 11, 20, 31, tzinfo=TZ)
    events, stale = calendars.load_all(cfg, *render.window(now.date(), 6))
    img = render.render(cfg, calendars.by_day(events), forecast, now, stale, panel=True)
    assert img.size == (1200, 1600)
    colours = {c for _, c in img.getcolors(maxcolors=1000)}
    assert colours <= set(PALETTE.values())
    assert {PALETTE["blue"], PALETTE["red"], PALETTE["green"]} <= colours


def test_hub_redraws_only_when_something_changes(tmp_path):
    cfg = _sample_cfg(tmp_path)
    forecast = weather.load_file(cfg.base_dir / "weather.json")
    out = tmp_path / "out"
    h1, drawn1 = hub.update(cfg, out, datetime(2026, 11, 11, 20, 0, tzinfo=TZ), forecast)
    h2, drawn2 = hub.update(cfg, out, datetime(2026, 11, 11, 20, 30, tzinfo=TZ), forecast)
    forecast.now += 1
    h3, drawn3 = hub.update(cfg, out, datetime(2026, 11, 11, 21, 0, tzinfo=TZ), forecast)
    h4, drawn4 = hub.update(cfg, out, datetime(2026, 11, 12, 0, 5, tzinfo=TZ), forecast)
    assert (drawn1, drawn2, drawn3, drawn4) == (True, False, True, True)
    assert h1 == h2 and len({h1, h3, h4}) == 3


def test_unreachable_calendar_uses_last_good_copy_and_is_flagged(tmp_path):
    cfg = _sample_cfg(tmp_path)
    first, last = date(2026, 11, 1), date(2026, 12, 5)
    events, stale = calendars.load_all(cfg, first, last)
    assert stale == []
    cfg.calendars[0].url = "missing.ics"
    again, stale = calendars.load_all(cfg, first, last)
    assert stale == ["Family"] and len(again) == len(events)


def test_busy_day_shows_a_more_line(tmp_path):
    cfg = _sample_cfg(tmp_path)
    now = datetime(2026, 11, 11, 12, 0, tzinfo=TZ)
    busy = ics(*[f"DTSTART;TZID=America/Toronto:20261114T{h:02d}0000\n"
                 f"DTEND;TZID=America/Toronto:20261114T{h:02d}3000\nSUMMARY:Thing {h}"
                 for h in range(8, 20)])
    grouped = days(busy, date(2026, 11, 1), date(2026, 12, 5))
    assert len(grouped[date(2026, 11, 14)]) == 12
    render.render(cfg, grouped, None, now)  # must not overflow or crash
