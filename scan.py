#!/usr/bin/env python3
"""Scan MSI SteelSeries KLC LED indices one at a time.

Usage:
  scan.py <idx> [rrggbb]      light one LED index (everything else off)
  scan.py --off               turn everything off
"""
import sys

import msikb as K


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    kb = K.LibUSB()
    try:
        arg = sys.argv[1]
        if arg == "--off":
            K.send_colors(kb, {led: (0, 0, 0) for led in K.all_leds()}, order=K.all_leds())
            print("off"); return
        idx = int(arg, 0)
        rgb = (255, 0, 0)
        if len(sys.argv) > 2:
            h = sys.argv[2].lstrip("#")
            rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        K.light_one(kb, idx, rgb)
        print(f"lit 0x{idx:02x} {rgb}")
    finally:
        kb.close()


if __name__ == "__main__":
    main()