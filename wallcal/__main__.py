"""Command line:  python -m wallcal check | render | run"""
import argparse
from datetime import datetime
from pathlib import Path

from . import calendars, config, hub, render, weather


def main() -> None:
    ap = argparse.ArgumentParser(prog="wallcal")
    ap.add_argument("command", choices=["check", "render", "run"],
                    help="check: test each calendar link. render: draw once and exit. "
                         "run: keep checking and serve the preview.")
    ap.add_argument("--config", help=f"settings file (default {config.DEFAULT_PATH})")
    ap.add_argument("--out", help="where to write the images (default <data_dir>/out)")
    ap.add_argument("--now", help="pretend it is this local time, e.g. 2026-11-11T20:30 (for testing)")
    ap.add_argument("--weather-file", help="use weather from this JSON file instead of the internet")
    args = ap.parse_args()

    cfg = config.load(args.config)
    out = Path(args.out).expanduser() if args.out else cfg.data_dir / "out"
    if args.command == "check":
        today = datetime.now(cfg.timezone).date()
        ok = calendars.check(cfg, *render.window(today, cfg.week_start))
        raise SystemExit(0 if ok else 1)
    if args.command == "run":
        hub.run(cfg, out)
        return
    now = datetime.fromisoformat(args.now).replace(tzinfo=cfg.timezone) if args.now else None
    forecast = weather.load_file(args.weather_file) if args.weather_file else None
    digest, redrawn = hub.update(cfg, out, now, forecast)
    print(f"{'Redrawn' if redrawn else 'No change'} ({digest}). Images in {out}")


if __name__ == "__main__":
    main()
