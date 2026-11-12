# Running on a Raspberry Pi with a monitor

The Pi becomes the hub: it fetches the calendars, draws the picture, and paints
it straight onto the HDMI screen. There is no desktop and no browser, which keeps
a Pi 3B+ comfortable and mirrors how the e-ink wall device will behave.

> This setup has been tested for everything that can be tested without a Pi
> (drawing, rotation, screen formats). The install script itself has not yet
> run on real hardware, so expect to report a hiccup or two the first time.

## 1. Put Raspberry Pi OS on the SD card

Use Raspberry Pi Imager on your Mac.

1. Choose your Pi model, then **Raspberry Pi OS Lite** (under "Raspberry Pi OS (other)").
2. When asked to customise, set a hostname (for example `wallcal`), a username
   and password, your Wi-Fi name and password, your time zone, and turn on SSH.
3. Write the card, put it in the Pi, connect the monitor, and power it on.

## 2. Install the calendar

From Terminal on your Mac (use the hostname and username you chose):

```
ssh yourname@wallcal.local
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/anikethsrao/Digital-Wall-Calendar.git
cd Digital-Wall-Calendar
bash pi/install.sh
```

The first run creates the settings file and stops. Edit it:

```
nano ~/.config/wallcal/config.toml
```

- Paste your calendar links, as on the Mac.
- Remove the `#` from the three `[screen]` lines.
- Set `rotate` to how far the monitor is turned clockwise: `0` if it is not
  turned, `90` or `270` if it stands on its side.

- Optional: to fill the whole monitor, set `[display]` `width` and `height` to the
  monitor's size as it hangs, for example `1080` and `1920` for a Full HD
  monitor on its side. Otherwise the 3:4 picture is centred with white bars.

Save (Ctrl+O, Enter, Ctrl+X) and run the script again:

```
bash pi/install.sh
```

The calendar should appear on the monitor within a minute, and again after every
reboot or power cut.

## 3. Day to day

- **See it from another computer:** http://wallcal.local:8000/
- **Upside down or sideways:** change `rotate` in the settings file, then
  `sudo systemctl restart wallcal`.
- **What is it doing:** `journalctl -u wallcal -f`
- **Update to the newest version:** `cd Digital-Wall-Calendar && git pull && bash pi/install.sh`

## What the install script changes on the Pi

- Installs `python3-venv` and `python3-pil`.
- Adds your user to the `video` and `tty` groups so it may draw on the screen.
- Adds a service, `wallcal`, that starts at boot and restarts if it stops.
- Turns off the login prompt on the monitor (it would draw over the calendar).
  SSH is unaffected. Undo with `sudo systemctl enable --now getty@tty1`.
