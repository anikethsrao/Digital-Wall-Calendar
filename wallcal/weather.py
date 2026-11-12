"""Weather from Open-Meteo (free, no account or key)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

from .config import Config

# WMO weather codes, grouped into plain words.
_WORDS = [
    ((0,), "Clear"), ((1,), "Mostly clear"), ((2,), "Partly cloudy"), ((3,), "Cloudy"),
    ((45, 48), "Fog"), ((51, 53, 55, 56, 57), "Drizzle"),
    ((61, 63, 65, 80, 81, 82), "Rain"), ((66, 67), "Freezing rain"),
    ((71, 73, 75, 77, 85, 86), "Snow"), ((95, 96, 99), "Thunderstorm"),
]


def words(code: int) -> str:
    for codes, text in _WORDS:
        if code in codes:
            return text
    return ""


@dataclass
class Day:
    date: str  # ISO date
    high: int
    low: int
    summary: str


@dataclass
class Forecast:
    place: str
    unit: str  # "C" or "F"
    now: int
    summary: str
    days: list[Day]


def fetch(cfg: Config) -> Forecast | None:
    """Current weather, or the last good copy if the service cannot be reached."""
    if cfg.weather is None:
        return None
    w = cfg.weather
    cache = cfg.data_dir / "cache" / "weather.json"
    query = urllib.parse.urlencode({
        "latitude": w.latitude, "longitude": w.longitude,
        "current": "temperature_2m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "temperature_unit": w.units, "timezone": str(cfg.timezone), "forecast_days": 4,
    })
    try:
        with urllib.request.urlopen(
            f"https://api.open-meteo.com/v1/forecast?{query}", timeout=30
        ) as resp:
            data = json.load(resp)
        d = data["daily"]
        forecast = Forecast(
            place=w.name,
            unit="F" if w.units == "fahrenheit" else "C",
            now=round(data["current"]["temperature_2m"]),
            summary=words(data["current"]["weather_code"]),
            days=[
                Day(d["time"][i], round(d["temperature_2m_max"][i]),
                    round(d["temperature_2m_min"][i]), words(d["weather_code"][i]))
                for i in range(len(d["time"]))
            ],
        )
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(asdict(forecast)))
        return forecast
    except Exception:
        return load_file(cache)


def load_file(path: Path) -> Forecast | None:
    try:
        raw = json.loads(Path(path).read_text())
        return Forecast(raw["place"], raw["unit"], raw["now"], raw["summary"],
                        [Day(**d) for d in raw["days"]])
    except Exception:
        return None
