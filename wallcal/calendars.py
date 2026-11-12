"""Fetches iCal feeds and turns them into simple per-day events."""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

from .config import CalendarSource, Config


@dataclass(frozen=True)
class Event:
    title: str
    calendar: str
    colour: str
    all_day: bool
    start: datetime | date  # local time for timed events, a date for all-day ones
    end: datetime | date    # exclusive

    def days(self) -> list[date]:
        """Every local calendar day this event touches."""
        if self.all_day:
            first, last = self.start, self.end - timedelta(days=1)
        else:
            first = self.start.date()
            last = self.end.date()
            # An event that ends exactly at midnight does not touch the next day.
            if self.end.time() == time(0) and self.end > self.start:
                last -= timedelta(days=1)
        last = max(first, last)
        return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _read(source: CalendarSource, cfg: Config) -> str:
    url = source.url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": "wallcal"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    path = Path(url).expanduser()
    if not path.is_absolute():
        path = cfg.base_dir / path
    return path.read_text()


def fetch_text(source: CalendarSource, cfg: Config) -> tuple[str, bool]:
    """Returns (ics text, fresh). Falls back to the last good copy if the fetch fails."""
    cache = cfg.data_dir / "cache" / f"{_slug(source.name)}.ics"
    try:
        text = _read(source, cfg)
        icalendar.Calendar.from_ical(text)  # refuse to cache something that is not a calendar
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text)
        return text, True
    except Exception:
        if cache.exists():
            return cache.read_text(), False
        raise


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-") or "calendar"


def parse(text: str, source: CalendarSource, first: date, last: date, tz: ZoneInfo) -> list[Event]:
    """Events from one feed that touch any day from `first` to `last` inclusive."""
    cal = icalendar.Calendar.from_ical(text)
    window_start = datetime.combine(first, time(0), tz)
    window_end = datetime.combine(last + timedelta(days=1), time(0), tz)
    events = []
    for item in recurring_ical_events.of(cal).between(window_start, window_end):
        if str(item.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = item["DTSTART"].dt
        if "DTEND" in item:
            end = item["DTEND"].dt
        elif "DURATION" in item:
            end = start + item["DURATION"].dt
        else:
            end = start + timedelta(days=1) if not isinstance(start, datetime) else start
        title = str(item.get("SUMMARY", "")).strip() or "(no title)"
        all_day = not isinstance(start, datetime)
        if all_day:
            if end <= start:
                end = start + timedelta(days=1)
        else:
            # Times with no zone ("floating") are read as local wall-clock time.
            start = start.replace(tzinfo=tz) if start.tzinfo is None else start.astimezone(tz)
            end = end.replace(tzinfo=tz) if end.tzinfo is None else end.astimezone(tz)
        ev = Event(title, source.name, source.colour, all_day, start, end)
        if any(first <= d <= last for d in ev.days()):
            events.append(ev)
    return events


def load_all(cfg: Config, first: date, last: date) -> tuple[list[Event], list[str]]:
    """All events in the window, plus the names of calendars that could not be refreshed."""
    events: list[Event] = []
    stale: list[str] = []
    for source in cfg.calendars:
        try:
            text, fresh = fetch_text(source, cfg)
        except Exception:
            stale.append(source.name)
            continue
        if not fresh:
            stale.append(source.name)
        events.extend(parse(text, source, first, last, cfg.timezone))
    return events, stale


def by_day(events: list[Event]) -> dict[date, list[Event]]:
    """Groups events by day: all-day first, then by start time."""
    days: dict[date, list[Event]] = {}
    for ev in events:
        for d in ev.days():
            days.setdefault(d, []).append(ev)

    def key(ev: Event):
        if ev.all_day:
            return (0, "", ev.title.lower())
        return (1, ev.start.isoformat(), ev.title.lower())

    for d in days:
        days[d].sort(key=key)
    return days
