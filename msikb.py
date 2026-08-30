"""
msikb — shared library for MSI SteelSeries KLC (USB 1038:1122) keyboards.

Protocol (reverse engineered):
  HID class SET_REPORT control transfer to interface 0:
    0x21 0x09, wValue=0x0300, 524-byte feature report:
      [0] opcode 0x0c  [1] 0x00  [2] mode 0x66 (kbd)  [3] 0x00
      then up to 102 four-byte slots (led index, R, G, B);
      unused slots use index 0xff so the controller ignores them.
  The controller parses at most 102 slots per report, so larger sets are
  split across several reports.
"""

import ctypes
import math
import time
import json
import os
import threading

VID = 0x1038
PID = 0x1122
IFACE = 0
REPORT_LEN = 524
OPCODE = 0x0C
KLC_MODE = 0x66
SLOTS_PER_REPORT = 102

# ------------------------------------------------------------------ libusb
class LibUSB:
    def __init__(self):
        self.lock = threading.Lock()
        self.lib = ctypes.CDLL("libusb-1.0.so.0")
        L = self.lib
        L.libusb_init.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        L.libusb_init.restype = ctypes.c_int
        L.libusb_open_device_with_vid_pid.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16]
        L.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        L.libusb_set_auto_detach_kernel_driver.argtypes = [ctypes.c_void_p, ctypes.c_int]
        L.libusb_set_auto_detach_kernel_driver.restype = ctypes.c_int
        L.libusb_claim_interface.argtypes = [ctypes.c_void_p, ctypes.c_int]
        L.libusb_claim_interface.restype = ctypes.c_int
        L.libusb_release_interface.argtypes = [ctypes.c_void_p, ctypes.c_int]
        L.libusb_release_interface.restype = ctypes.c_int
        L.libusb_control_transfer.argtypes = [
            ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint16,
            ctypes.c_uint16, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint16, ctypes.c_uint]
        L.libusb_control_transfer.restype = ctypes.c_int
        L.libusb_close.argtypes = [ctypes.c_void_p]
        L.libusb_exit.argtypes = [ctypes.c_void_p]

        self.ctx = ctypes.c_void_p()
        if L.libusb_init(ctypes.byref(self.ctx)) != 0:
            raise RuntimeError("libusb_init failed")
        self.dev = L.libusb_open_device_with_vid_pid(self.ctx, VID, PID)
        if not self.dev:
            L.libusb_exit(self.ctx)
            raise RuntimeError("Keyboard not found (is 1038:1122 present?)")
        L.libusb_set_auto_detach_kernel_driver(self.dev, 1)

    def send_report(self, payload):
        with self.lock:
            return self._send_report(payload)

    def _send_report(self, payload):
        buf = (ctypes.c_ubyte * len(payload)).from_buffer_copy(bytearray(payload))
        self.lib.libusb_claim_interface(self.dev, IFACE)
        n = self.lib.libusb_control_transfer(
            self.dev, 0x21, 0x09, 0x0300, IFACE, buf, len(payload), 2000)
        self.lib.libusb_release_interface(self.dev, IFACE)
        return n

    def close(self):
        if self.dev:
            self.lib.libusb_close(self.dev)
            self.dev = None
        if self.ctx:
            self.lib.libusb_exit(self.ctx)
            self.ctx = None


# ----------------------------------------------------------------- protocol
def build_report_packed(leds, mode=KLC_MODE):
    """leds: list of (led_index, r, g, b); slots filled sequentially."""
    report = bytearray(REPORT_LEN)
    report[0] = OPCODE
    report[1] = 0x00
    report[2] = mode
    report[3] = 0x00
    for i in range((REPORT_LEN - 4) // 4):
        report[4 + i * 4] = 0xff
    for i, (idx, (r, g, b)) in enumerate(leds):
        pos = 4 + i * 4
        report[pos] = idx
        report[pos + 1] = r
        report[pos + 2] = g
        report[pos + 3] = b
    return report


def reports_for(colors, mode=KLC_MODE):
    """colors: list of (led_index, (r, g, b)) in command order."""
    reps = []
    for i in range(0, len(colors), SLOTS_PER_REPORT):
        chunk = colors[i:i + SLOTS_PER_REPORT]
        reps.append(build_report_packed(chunk, mode))
    return reps


def send_colors(kb, colors_map, order=None):
    """colors_map: {led_index: (r,g,b)}. Sends chunked feature reports."""
    if order is None:
        order = list(colors_map.keys())
    leds = [(led, colors_map[led]) for led in order if led in colors_map]
    for rep in reports_for(leds):
        kb.send_report(rep)


def light_one(kb, idx, rgb=(255, 0, 0)):
    """Light one LED index, everything else off/blank."""
    rep = bytearray(REPORT_LEN)
    rep[0] = OPCODE; rep[1] = 0; rep[2] = KLC_MODE; rep[3] = 0
    for i in range((REPORT_LEN - 4) // 4):
        rep[4 + i * 4] = 0xff
    rep[4] = idx & 0xff
    rep[5] = rgb[0]; rep[6] = rgb[1]; rep[7] = rgb[2]
    kb.send_report(rep)


# --------------------------------------------------------- layout & key map
# LED indices are the standard USB HID keyboard usage codes, confirmed by
# scanning (Home=0x4a, End=0x4d, Fn=0xf0).
HID = {
    "esc": 0x29, "f1": 0x3a, "f2": 0x3b, "f3": 0x3c, "f4": 0x3d, "f5": 0x3e,
    "f6": 0x3f, "f7": 0x40, "f8": 0x41, "f9": 0x42, "f10": 0x43, "f11": 0x44,
    "f12": 0x45, "prtsc": 0x46,
    "`": 0x35, "1": 0x1e, "2": 0x1f, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27, "-": 0x2d,
    "=": 0x2e, "back": 0x2a,
    "tab": 0x2b, "q": 0x14, "w": 0x1a, "e": 0x08, "r": 0x15, "t": 0x17,
    "y": 0x1c, "u": 0x18, "i": 0x0c, "o": 0x12, "p": 0x13, "[": 0x2f,
    "]": 0x30, "\\": 0x31,
    "caps": 0x39, "a": 0x04, "s": 0x16, "d": 0x07, "f": 0x09, "g": 0x0a,
    "h": 0x0b, "j": 0x0d, "k": 0x0e, "l": 0x0f, ";": 0x33, "'": 0x34,
    "enter": 0x28,
    "lshift": 0xe1, "iso": 0x64, "z": 0x1d, "x": 0x1b, "c": 0x06, "v": 0x19, "b": 0x05,
    "n": 0x11, "m": 0x10, ",": 0x36, ".": 0x37, "/": 0x38, "rshift": 0xe5,
    "lctrl": 0xe0, "win": 0xe3, "lalt": 0xe2, "space": 0x2c,
    "ralt": 0xe6, "fn": 0xf0, "rctrl": 0xe4,
    "ins": 0x49, "home": 0x4a, "pgup": 0x4b,
    "del": 0x4c, "end": 0x4d, "pgdn": 0x4e,
    "right": 0x4f, "left": 0x50, "down": 0x51, "up": 0x52,
}

# Physical GS65 layout. rows = main block; right of it a 2x3 nav column;
# arrows sit below the nav column (beside the bottom rows).
ROWS = [
    ["esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12", "prtsc"],
    ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "back"],
    ["tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]", "\\"],
    ["caps", "a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'", "enter"],
    ["lshift", "iso", "z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "rshift"],
    ["lctrl", "win", "lalt", "space", "ralt", "fn", "rctrl"],
]
NAV = [["ins", "del"], ["home", "end"], ["pgup", "pgdn"]]
ARROWS = ["up", "left", "down", "right"]

WIDTHS = {
    "back": 2, "tab": 1.5, "\\": 1.5, "caps": 1.75, "enter": 2.25,
    "lshift": 1.75, "iso": 1.25, "rshift": 2.75, "lctrl": 1.25,
    "win": 1.25, "lalt": 1.25, "space": 6.5, "ralt": 1.25, "fn": 1.25,
    "rctrl": 1.25,
}


def layout_keys():
    """Flatten layout into list of (led_index, key_name, x, y)."""
    keys = []
    for r, row in enumerate(ROWS):
        x = 0.0
        for name in row:
            led = HID[name]
            keys.append((led, name, x, r))
            x += WIDTHS.get(name, 1.0)
    for r, col in enumerate(NAV):
        for i, name in enumerate(col):
            led = HID[name]
            keys.append((led, name, 15.0 + i * 0.9, r + 1))
    for i, name in enumerate(ARROWS):
        led = HID[name]
        keys.append((led, name, 15.9 + (i - 1) * 0.9, 4 + (i == 0)))
    return keys


def all_leds():
    return [led for led, *_ in layout_keys()]


COLOR_LABELS = {
    "off": (0, 0, 0), "black": (0, 0, 0), "red": (255, 0, 0),
    "orange": (255, 100, 0), "yellow": (255, 255, 0), "green": (0, 255, 0),
    "cyan": (0, 255, 255), "sky": (0, 255, 255), "blue": (0, 0, 255),
    "purple": (255, 0, 255), "pink": (255, 0, 128), "white": (255, 255, 255),
}


def parse_color(s):
    s = s.lower()
    if s in COLOR_LABELS:
        return COLOR_LABELS[s]
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    if len(s) == 3:
        return (int(s[0] * 2, 16), int(s[1] * 2, 16), int(s[2] * 2, 16))
    raise ValueError(f"unknown color: {s}")


# ----------------------------------------------------------------- effects
def hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return tuple(int(c * 255) for c in ((v, t, p), (q, v, p), (p, v, t),
                 (p, q, v), (t, p, v), (v, p, q))[i])


def render_frame(config, t):
    """config dict -> {led: (r,g,b)} for anchored t (seconds)."""
    mode = config.get("mode", "static")
    speed = float(config.get("speed", 1.0))
    colors = {int(k): parse_color(v) for k, v in config.get("colors", {}).items()}
    leds = [led for led, *_ in layout_keys()]
    xmax = max(x for _, _, x, _ in layout_keys()) or 1.0

    out = {}
    for led, name, x, y in layout_keys():
        if mode == "off":
            rgb = (0, 0, 0)
        elif mode == "static":
            rgb = colors.get(led, (0, 0, 0))
        elif mode == "breathe":
            base = colors.get(led, (255, 255, 255))
            mult = (math.sin(t * 2 * math.pi * speed / 2.0) + 1.0) / 2.0
            mult = 0.15 + 0.85 * mult
            rgb = tuple(int(c * mult) for c in base)
        elif mode == "rainbow":
            h = ((x / xmax) + t * speed * 0.05) % 1.0
            rgb = hsv(h, 0.9, 1.0)
        elif mode == "wave":
            ph = (x / xmax) * 8 - t * speed * 2.0
            h = (0.5 + 0.5 * math.sin(ph * math.pi)) % 1.0
            rgb = hsv(h, 0.9, 1.0)
        elif mode == "starlight":
            base = colors.get(led, (200, 220, 255))
            tw = (math.sin((led * 12.9898 % 1.0) * t * speed * 0.7) + 1.0) / 2.0
            rgb = tuple(int(c * (0.15 + 0.85 * tw)) for c in base)
        else:
            rgb = colors.get(led, (0, 0, 0))
        out[led] = rgb
    return out


# ------------------------------------------------------------- persistence
KEYMAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keymap.json")


def load_keymap():
    """Load per-key LED overrides {key_name: led_index}."""
    try:
        with open(KEYMAP_FILE) as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.items()}
    except Exception:
        return {}


def save_keymap(overrides):
    with open(KEYMAP_FILE, "w") as f:
        json.dump(overrides, f, indent=2)


def effective_map():
    """Actual led per key: defaults with user keymap overrides applied."""
    overrides = load_keymap()
    m = dict(HID)
    m.update(overrides)
    return m