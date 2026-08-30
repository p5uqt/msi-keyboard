#!/usr/bin/env python3
"""Слушает нажатия клавиатуры MSI и печатает USB-коды клавиш.

  keyev.py              слушать ~25 c, печатать каждый PRESS (код + имя)
  keyev.py <сек>        задать время
  keyev.py --list       показать HID-коды всех клавиш
"""
import os
import select
import struct
import sys
import time

try:
    import msikb as K
    CODE2NAME = {v: k for k, v in K.HID.items()}
except Exception:
    CODE2NAME = {}


def find_msi():
    for dev in sorted(os.listdir("/dev/input")):
        if not dev.startswith("event"):
            continue
        path = "/dev/input/" + dev
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        try:
            import fcntl
            name = fcntl.ioctl(fd, 0x80044506, b"\0" * 256).rstrip(b"\0")
            if b"MSI" in name:
                return path
        finally:
            os.close(fd)
    return None


def main():
    if "--list" in sys.argv:
        for code in sorted(CODE2NAME):
            print(f"  0x{code:02x}  {CODE2NAME[code]}")
        return
    dur = 25
    if len(sys.argv) > 1:
        try:
            dur = float(sys.argv[1])
        except ValueError:
            pass
    path = find_msi()
    if not path:
        print("MSI keyboard input device not found"); return
    print(f"слушаю {path} ... нажми нужную клавишу")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    ev = struct.Struct("QQHHi")
    end = time.time() + dur
    try:
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            try:
                data = os.read(fd, ev.size * 16)
            except BlockingIOError:
                continue
            for off in range(0, len(data) - ev.size + 1, ev.size):
                _, _, t, code, val = ev.unpack_from(data, off)
                if t == 1 and val == 1:
                    name = CODE2NAME.get(code, "?")
                    print(time.strftime("%H:%M:%S"), f"PRESS 0x{code:02x} ({name})", flush=True)
    finally:
        os.close(fd)
    print("готово")


if __name__ == "__main__":
    main()