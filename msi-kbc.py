#!/usr/bin/env python3
"""CLI for MSI SteelSeries KLC keyboard backlight.

usage:
  msi-kbc.py <color>              set whole keyboard (name|#rrggbb|rrggbb)
  msi-kbc.py --key <name> <color> set one key (names: a,b,c...,f1,esc,enter,...)
  msi-kbc.py --keys               list key names
  msi-kbc.py --off                turn backlight off
  msi-kbc.py --rainbow            animated rainbow (Ctrl-C to stop)
  msi-kbc.py --pulse <color> [speed]  breathing effect
"""
import sys
import time

import msikb as K


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "--keys":
        for name, led in K.HID.items():
            print(f"  {name:8} 0x{led:02x}")
        sys.exit(0)

    kb = K.LibUSB()
    try:
        if args[0] == "--off":
            K.send_colors(kb, {led: (0, 0, 0) for led in K.all_leds()}, order=K.all_leds())
            print("off")
        elif args[0] == "--key":
            if len(args) < 3:
                print(__doc__); return
            name = args[1]
            rgb = K.parse_color(args[2])
            try:
                led = K.effective_map()[name]
            except KeyError:
                print(f"no such key: {name}"); return
            K.light_one(kb, led, rgb)
            print(f"{name} (0x{led:02x}) = {rgb}")
        elif args[0] == "--rainbow":
            t = 0.0
            try:
                while True:
                    cfg = {"mode": "rainbow", "speed": 1.0}
                    K.send_colors(kb, K.render_frame(cfg, t))
                    time.sleep(0.03)
                    t += 0.03
            except KeyboardInterrupt:
                pass
        elif args[0] == "--pulse":
            if len(args) < 2:
                print(__doc__); return
            base = K.parse_color(args[1])
            speed = float(args[2]) if len(args) > 2 else 1.0
            t = 0.0
            try:
                while True:
                    cfg = {"mode": "breathe", "speed": speed,
                           "colors": {str(led): "#%02x%02x%02x" % base for led in K.all_leds()}}
                    K.send_colors(kb, K.render_frame(cfg, t))
                    time.sleep(0.05)
                    t += 0.05
            except KeyboardInterrupt:
                pass
        else:
            rgb = K.parse_color(args[0])
            colors = {led: rgb for led in K.all_leds()}
            K.send_colors(kb, colors, order=K.all_leds())
            print(f"uniform {rgb}")
    finally:
        kb.close()


if __name__ == "__main__":
    main()