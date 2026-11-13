"""The hub: checks the calendars, redraws only when something changed, serves the picture."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import calendars, render, screen, weather
from .config import Config

PAGE = """<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="60">
<title>Wall calendar preview</title>
<style>body{margin:0;background:#888;font:14px system-ui;text-align:center;color:#fff}
img{height:calc(100vh - 40px);margin-top:8px;box-shadow:0 2px 12px #0006}a{color:#fff}</style>
<img src="IMG?h=HASH" alt="Calendar">
<p>Last checked CHECKED · <a href="/">panel colours</a> · <a href="/smooth.html">smooth</a></p>"""


def state_hash(cfg: Config, events, forecast, today, stale) -> str:
    """A fingerprint of everything on the page. Same fingerprint means nothing to redraw."""
    payload = {
        "size": [cfg.width, cfg.height], "today": today.isoformat(), "stale": sorted(stale),
        "events": sorted([e.title, e.calendar, e.colour, e.all_day, e.start.isoformat(),
                          e.end.isoformat()] for e in events),
        "weather": asdict(forecast) if forecast else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def update(cfg: Config, out: Path, now: datetime | None = None,
           forecast_override=None) -> tuple[str, bool]:
    """One check. Returns (fingerprint, whether the picture was redrawn)."""
    now = now or datetime.now(cfg.timezone)
    first, last = render.window(now.date(), cfg.week_start)
    events, stale = calendars.load_all(cfg, first, last)
    forecast = forecast_override or weather.fetch(cfg)
    digest = state_hash(cfg, events, forecast, now.date(), stale)

    out.mkdir(parents=True, exist_ok=True)
    status_file = out / "status.json"
    try:
        status = json.loads(status_file.read_text())
    except Exception:
        status = {}
    redrawn = status.get("hash") != digest or not (out / "panel.png").exists()
    if redrawn:
        days = calendars.by_day(events)
        render.render(cfg, days, forecast, now, stale, panel=True).save(out / "panel.png")
        render.render(cfg, days, forecast, now, stale, panel=False).save(out / "preview.png")
        status["drawn"] = now.isoformat(timespec="seconds")
    status.update(hash=digest, checked=now.isoformat(timespec="seconds"), stale=stale)
    status_file.write_text(json.dumps(status, indent=2))
    checked = now.strftime("%b %d, %H:%M")
    for name, image in (("index.html", "panel.png"), ("smooth.html", "preview.png")):
        (out / name).write_text(
            PAGE.replace("IMG", image).replace("HASH", digest).replace("CHECKED", checked))
    return digest, redrawn


def paint(cfg: Config, out: Path) -> None:
    """Puts the current picture on the attached screen, if one is set up."""
    if cfg.screen_device is None:
        return
    try:
        screen.show(out / "panel.png", cfg.screen_device, cfg.screen_rotate)
    except Exception as exc:
        print(f"Screen could not be updated: {type(exc).__name__}: {exc}", flush=True)


def run(cfg: Config, out: Path) -> None:
    """Checks forever and serves the preview page at http://localhost:<port>/."""
    try:
        update(cfg, out)
    except Exception as exc:  # e.g. no network yet just after boot
        print("first check failed:", exc, flush=True)
    paint(cfg, out)
    handler = partial(SimpleHTTPRequestHandler, directory=str(out))
    server = ThreadingHTTPServer(("0.0.0.0", cfg.port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Preview at http://localhost:{cfg.port}/  (checking every {cfg.check_minutes} min)",
          flush=True)
    while True:
        time.sleep(cfg.check_minutes * 60)
        try:
            digest, redrawn = update(cfg, out)
            print(datetime.now().strftime("%H:%M"), "redrawn" if redrawn else "no change", digest,
                  flush=True)
            if redrawn:
                paint(cfg, out)
        except Exception as exc:  # keep running through any one bad check
            print("check failed:", exc, flush=True)
