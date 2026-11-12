# Digital Wall Calendar

A household wall calendar. A small hub service reads everyone's calendars, draws
the month as one picture, and every screen just shows that picture. The same
picture will later go to a battery-powered colour e-ink panel on the wall.

This is MK1, Stage 1: the software running on a Mac.

## What it does

- Reads any number of read-only iCal links (Apple, Google, Outlook and others).
- Draws a portrait month view with one colour per calendar, plus the weather.
- Uses only the six colours a colour e-ink panel can show.
- Redraws only when a calendar, the weather or the date changes.
- Keeps the last good copy of each calendar if the internet drops, and says so on the picture.

## Try it with made-up calendars

Needs Python 3.11 or newer (check with `python3 --version`).

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m wallcal render --config samples/config.toml --out out \
    --now 2026-11-11T20:31 --weather-file samples/weather.json
open out/panel.png
```

## Use your own calendars

1. Copy `config.example.toml` to `~/.config/wallcal/config.toml`.
2. Paste in each calendar's private iCal link and pick its colour.
3. Run `python -m wallcal run` and open http://localhost:8000/.

Your links stay in that file on your computer. They are never part of this repository.

## Files it writes

In `~/.local/share/wallcal/out/`:

- `panel.png`: exactly what the e-ink panel will show (six flat colours).
- `preview.png`: the same page with smooth text, for a normal screen.
- `status.json`: a fingerprint of the page. The wall device will read this to
  learn whether anything changed before it downloads a new picture.

## Tests

```
pip install pytest
python -m pytest
```

## Weather

Weather comes from Open-Meteo, which is free and needs no account.

## Fonts

Inter, under the SIL Open Font License (see `wallcal/fonts/OFL.txt`).
