"""Loads settings from a TOML file that lives outside the code repository."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_PATH = Path("~/.config/wallcal/config.toml").expanduser()

# The six colours a colour e-ink panel can show.
PALETTE = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (200, 30, 30),
    "yellow": (240, 200, 0),
    "blue": (30, 70, 180),
    "green": (30, 130, 60),
}
EVENT_COLOURS = ["blue", "red", "green", "yellow", "black"]


@dataclass
class CalendarSource:
    name: str
    url: str
    colour: str


@dataclass
class Weather:
    name: str
    latitude: float
    longitude: float
    units: str = "celsius"


@dataclass
class Config:
    timezone: ZoneInfo
    week_start: int  # 6 = Sunday, 0 = Monday (Python weekday numbers)
    width: int = 1200
    height: int = 1600
    calendars: list[CalendarSource] = field(default_factory=list)
    weather: Weather | None = None
    clock: int = 12  # 12 or 24 hour times
    check_minutes: int = 5
    port: int = 8000
    data_dir: Path = Path("~/.local/share/wallcal").expanduser()
    base_dir: Path = Path(".")


def load(path: str | os.PathLike | None = None) -> Config:
    p = Path(path).expanduser() if path else DEFAULT_PATH
    if not p.exists():
        raise SystemExit(
            f"No settings file at {p}. Copy config.example.toml there and fill it in."
        )
    raw = tomllib.loads(p.read_text())

    week_start = {"sunday": 6, "monday": 0}[raw.get("week_start", "sunday").lower()]
    display = raw.get("display", {})
    hub = raw.get("hub", {})

    calendars = []
    for i, c in enumerate(raw.get("calendar", [])):
        colour = c.get("colour", EVENT_COLOURS[i % len(EVENT_COLOURS)]).lower()
        if colour not in PALETTE or colour == "white":
            raise SystemExit(
                f"Calendar '{c.get('name')}': colour must be one of "
                f"{', '.join(k for k in PALETTE if k != 'white')}."
            )
        calendars.append(CalendarSource(c["name"], c["url"], colour))
    if not calendars:
        raise SystemExit(f"{p} lists no calendars. Add at least one [[calendar]].")

    weather = None
    if "weather" in raw:
        w = raw["weather"]
        weather = Weather(
            w["name"], float(w["latitude"]), float(w["longitude"]),
            w.get("units", "celsius").lower(),
        )

    cfg = Config(
        timezone=ZoneInfo(raw["timezone"]),
        week_start=week_start,
        width=int(display.get("width", 1200)),
        height=int(display.get("height", 1600)),
        calendars=calendars,
        weather=weather,
        clock=int(raw.get("clock", 12)),
        check_minutes=int(hub.get("check_minutes", 5)),
        port=int(hub.get("port", 8000)),
        base_dir=p.parent,
    )
    if "data_dir" in hub:
        cfg.data_dir = Path(hub["data_dir"]).expanduser()
    return cfg
