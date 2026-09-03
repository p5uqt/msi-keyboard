# msi-keyboard

Per-key RGB backlight control for **MSI GS65 Stealth 9SF** (SteelSeries KLC keyboard, USB `1038:1122`) on Linux.

> **Only tested and confirmed on MSI GS65 Stealth 9SF.** Other MSI models may have different LED layouts or protocols and are **not supported**.

Reverse-engineered HID protocol. No official SDK — pure `libusb` control transfers.

## Requirements

- Python 3.8+
- `libusb-1.0` (`libusb-1.0.so.0`)
- Root or [udev rule](#udev-rule) for USB access

### Install libusb

```bash
# Debian / Ubuntu
sudo apt install libusb-1.0-0

# Arch
sudo pacman -S libusb

# Fedora
sudo dnf install libusb1
```

### udev rule (to avoid running as root)

Create `/etc/udev/rules.d/99-msi-kbc.rules`:

```
SUBSYSTEM=="usb", ATTR{idVendor}=="1038", ATTR{idProduct}=="1122", MODE="0666"
```

Then reload:

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Usage

### CLI — `msi-kbc.py`

Set the whole keyboard to a single color:

```bash
python3 msi-kbc.py red
python3 msi-kbc.py "#00aaff"
python3 msi-kbc.py ff0044
```

Light one key:

```bash
python3 msi-kbc.py --key w red
python3 msi-kbc.py --key space "#00ff66"
```

List all key names and their LED indices:

```bash
python3 msi-kbc.py --keys
```

Animated rainbow:

```bash
python3 msi-kbc.py --rainbow
```

Breathing / pulse effect:

```bash
python3 msi-kbc.py --pulse blue
python3 msi-kbc.py --pulse "#ff0088" 2.0   # speed = 2.0
```

Turn off:

```bash
python3 msi-kbc.py --off
```

### Web UI — `server.py`

Start the visual editor:

```bash
python3 server.py          # default port 8765
python3 server.py 3000     # custom port
```

Open `http://localhost:8765` in a browser. Features:

- Click / drag to paint keys with any color
- Right-click to erase
- Modes: static, rainbow, wave, breathe, starlight, off
- Speed and brightness sliders
- Key probe mode — find the correct LED index for any key

### Workspace indicator — `wsrgb.py`

Lights the number-row keys to show the active Hyprland workspace:

```bash
python3 wsrgb.py                                    # white base, auto-cycle workspace color
python3 wsrgb.py --base "#2255aa" --ws red green blue  # per-workspace colors
python3 wsrgb.py --off                               # turn off and exit
```

### LED scanner — `scan.py`

Light a single LED index to identify which physical key it maps to:

```bash
python3 scan.py 0x4a          # light index 0x4a in red
python3 scan.py 0x4a "#00ff00"  # light it green
python3 scan.py --off
```

### Key event listener — `keyev.py`

Listen for keypresses and print their USB HID codes (useful for finding unmapped keys):

```bash
python3 keyev.py          # listen for 25 seconds
python3 keyev.py 10       # listen for 10 seconds
python3 keyev.py --list   # show all known HID codes
```

## Library — `msikb.py`

Import it in your own scripts:

```python
import msikb as K

kb = K.LibUSB()

# Set all keys to blue
colors = {led: (0, 0, 255) for led in K.all_leds()}
K.send_colors(kb, colors, order=K.all_leds())

# Light a single key
K.light_one(kb, K.HID["w"], (255, 0, 0))

# Render an animated frame
import time
frame = K.render_frame({"mode": "rainbow", "speed": 1.0}, time.time())
K.send_colors(kb, frame)

kb.close()
```

### Color parsing

```python
K.parse_color("red")         # (255, 0, 0)
K.parse_color("#00ff88")     # (0, 255, 136)
K.parse_color("ff0044")      # (255, 0, 68)
K.parse_color("abc")         # (170, 187, 204)
```

### Effects

```python
K.render_frame({"mode": "breathe", "speed": 1.0,
                "colors": {"28": "#ff0000"}}, t)
K.render_frame({"mode": "wave", "speed": 2.0}, t)
K.render_frame({"mode": "starlight", "colors": {"28": "#0088ff"}}, t)
K.render_frame({"mode": "static", "colors": {"28": "#ff0000"}}, t)
K.render_frame({"mode": "off"}, t)
```

## Project structure

```
msikb.py       core library — protocol, layout, effects, color utils
msi-kbc.py     CLI tool
server.py      web UI (single-file, no deps beyond stdlib)
wsrgb.py       Hyprland workspace indicator
scan.py        LED index scanner
keyev.py       keypress listener
keymap.json    per-key LED overrides (edited by the web UI)
```

## Notes

- Inspired by [msi-perkeyrgb](https://github.com/Askannz/msi-perkeyrgb), but unlike it, **the keyboard does not flicker when changing colors** — updates are sent as packed reports in a single transfer.
- Only one process should talk to the keyboard at a time (the libusb handle is exclusive).
- The protocol supports up to 102 LED slots per HID report; the library auto-chunks larger sets.
- Tested on MSI GS65 Stealth 9SF. Should work on other SteelSeries KLC keyboards with VID:PID `1038:1122`.

## License

MIT
