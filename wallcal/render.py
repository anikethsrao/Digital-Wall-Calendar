"""Draws the month calendar as one image, sized for the wall panel."""
from __future__ import annotations

import calendar as pycal
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .calendars import Event
from .config import PALETTE, Config
from .weather import Forecast

FONTS = Path(__file__).parent / "fonts"
BLACK, WHITE, RED = PALETTE["black"], PALETTE["white"], PALETTE["red"]


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Inter-{weight}.otf"), size)


def month_grid(today: date, week_start: int) -> list[list[date]]:
    """The weeks to show for today's month, each a list of seven dates."""
    return pycal.Calendar(firstweekday=week_start).monthdatescalendar(today.year, today.month)


def clock(dt: datetime, hours: int) -> str:
    if hours == 24:
        return dt.strftime("%H:%M")
    h = dt.hour % 12 or 12
    suffix = "a" if dt.hour < 12 else "p"
    return f"{h}{suffix}" if dt.minute == 0 else f"{h}:{dt.minute:02d}{suffix}"


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: float) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: float, lines: int) -> list[str]:
    """Word-wraps onto at most `lines` lines; the last one is cut with an ellipsis if needed."""
    out: list[str] = []
    words = text.split()
    while words and len(out) < lines - 1:
        line = words[0]
        if draw.textlength(line, font=font) > width:
            break  # a single word too long to wrap: cut it on this line instead
        i = 1
        while i < len(words) and draw.textlength(f"{line} {words[i]}", font=font) <= width:
            line, i = f"{line} {words[i]}", i + 1
        out.append(line)
        words = words[i:]
    if words:
        out.append(_fit(draw, " ".join(words), font, width))
    return out


def render(cfg: Config, days: dict[date, list[Event]], forecast: Forecast | None,
           now: datetime, stale: list[str] | None = None, panel: bool = False) -> Image.Image:
    """`panel=True` gives exactly what colour e-ink shows: six flat colours, no smoothing."""
    W, H = cfg.width, cfg.height
    s = W / 1200  # everything scales with the panel width
    px = lambda v: round(v * s)
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    if panel:
        draw.fontmode = "1"
    today = now.date()
    m = px(36)

    # Header: month on the left, weather on the right.
    draw.text((m, px(34)), now.strftime("%B"), font=_font("Bold", px(92)), fill=BLACK)
    draw.text((m + px(4), px(138)), now.strftime("%Y"), font=_font("Regular", px(34)), fill=BLACK)
    if forecast:
        right = W - m
        temp = f"{forecast.now}°{forecast.unit}"
        draw.text((right, px(34)), temp, font=_font("Bold", px(72)), fill=BLACK, anchor="ra")
        line = " · ".join(t for t in (forecast.summary, forecast.place) if t)
        draw.text((right, px(118)), line, font=_font("SemiBold", px(26)), fill=BLACK, anchor="ra")
        parts = []
        for d in forecast.days[:4]:
            dd = date.fromisoformat(d.date)
            if dd < today:
                continue
            label = "Today" if dd == today else dd.strftime("%a")
            parts.append(f"{label} {d.high}°/{d.low}°")
        draw.text((right, px(154)), "   ".join(parts[:3]), font=_font("Regular", px(22)),
                  fill=BLACK, anchor="ra")

    # Grid.
    weeks = month_grid(today, cfg.week_start)
    top, footer = px(250), px(64)
    grid_h = H - top - footer
    col_w, row_h = (W - 2 * m) / 7, grid_h / len(weeks)
    f_head = _font("SemiBold", px(22))
    for i, d in enumerate(weeks[0]):
        draw.text((m + i * col_w + px(8), top - px(34)), d.strftime("%a").upper(),
                  font=f_head, fill=BLACK)

    f_day, f_ev, f_evb = _font("Bold", px(26)), _font("Regular", px(19)), _font("SemiBold", px(19))
    line_h, ev_top = px(27), px(46)
    max_lines = int((row_h - ev_top - px(4)) // line_h)

    for r, week in enumerate(weeks):
        y = top + r * row_h
        for c, d in enumerate(week):
            x = m + c * col_w
            label = str(d.day) if d.month == today.month else f"{d.strftime('%b')} {d.day}"
            if d == today:
                tw = draw.textlength(label, font=f_day)
                draw.rounded_rectangle((x + px(4), y + px(6), x + px(20) + tw, y + px(40)),
                                       radius=px(8), fill=BLACK)
                draw.text((x + px(12), y + px(8)), label, font=f_day, fill=WHITE)
            else:
                font = f_day if d.month == today.month else _font("Regular", px(22))
                draw.text((x + px(8), y + px(8)), label, font=font, fill=BLACK)

            events = days.get(d, [])
            shown = events if len(events) <= max_lines else events[:max_lines - 1]
            # Quiet days have room to wrap long titles onto a second line.
            per_event = 2 if len(events) * 2 <= max_lines else 1
            ey = y + ev_top
            inner = col_w - px(10)
            for ev in shown:
                colour = PALETTE[ev.colour]
                starts_today = ev.all_day or ev.start.date() == d
                if ev.all_day or not starts_today:
                    # All-day events, and later days of a multi-day event, are solid bars.
                    lines = _wrap(draw, ev.title, f_evb, inner - px(10), per_event)
                    bottom = ey + line_h * len(lines) - px(3)
                    draw.rounded_rectangle((x + px(4), ey, x + px(4) + inner, bottom),
                                           radius=px(4), fill=colour)
                    ink = BLACK if ev.colour == "yellow" else WHITE
                    font, tx = f_evb, x + px(9)
                else:
                    text = f"{clock(ev.start, cfg.clock)} {ev.title}"
                    lines = _wrap(draw, text, f_ev, inner - px(12), per_event)
                    draw.rectangle((x + px(4), ey + px(1), x + px(9),
                                    ey + line_h * len(lines) - px(5)), fill=colour)
                    ink, font, tx = BLACK, f_ev, x + px(14)
                for line in lines:
                    draw.text((tx, ey + px(1)), line, font=font, fill=ink)
                    ey += line_h
            if len(shown) < len(events):
                draw.text((x + px(9), ey + px(1)), f"+{len(events) - len(shown)} more",
                          font=f_evb, fill=BLACK)

    # Grid lines on top of the cells.
    for r in range(len(weeks) + 1):
        y = round(top + r * row_h)
        draw.line((m, y, W - m, y), fill=BLACK, width=max(1, px(2)))
    for c in range(8):
        x = round(m + c * col_w)
        draw.line((x, top, x, top + grid_h), fill=BLACK, width=max(1, px(2)))

    # Footer: which colour is which calendar, and when this was drawn.
    fy = H - footer + px(18)
    f_foot = _font("SemiBold", px(22))
    x = m
    for cal in cfg.calendars:
        draw.rounded_rectangle((x, fy + px(2), x + px(22), fy + px(24)), radius=px(4),
                               fill=PALETTE[cal.colour])
        draw.text((x + px(30), fy), cal.name, font=f_foot, fill=BLACK)
        x += px(30) + draw.textlength(cal.name, font=f_foot) + px(28)
    stamp = "Drawn " + now.strftime("%a %b ") + f"{now.day}, " + (
        now.strftime("%H:%M") if cfg.clock == 24
        else f"{now.hour % 12 or 12}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}")
    if stale:
        stamp = "Could not refresh: " + ", ".join(stale) + "   " + stamp
    draw.text((W - m, fy), stamp, font=_font("Regular", px(22)),
              fill=RED if stale else BLACK, anchor="ra")

    return to_panel(img) if panel else img


def to_panel(img: Image.Image) -> Image.Image:
    """Snaps every pixel to the nearest of the six panel colours."""
    pal = Image.new("P", (1, 1))
    flat = [v for rgb in PALETTE.values() for v in rgb]
    pal.putpalette(flat + flat[:3] * (256 - len(PALETTE)))
    return img.quantize(palette=pal, dither=Image.Dither.NONE).convert("RGB")


def window(today: date, week_start: int) -> tuple[date, date]:
    """First and last date visible on the month page."""
    weeks = month_grid(today, week_start)
    return weeks[0][0], weeks[-1][-1]
