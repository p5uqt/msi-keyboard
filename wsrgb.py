#!/usr/bin/env python3
"""Подсветка клавиатуры + индикатор активного рабочего стола (Hyprland).

  wsrgb.py [--base ЦВЕТ] [--ws ЦВЕТ1 [ЦВЕТ2 ...]] [--off] [-h|--help]

  wsrgb.py --base #2255aa --ws #ff8800
                              вся клавиатура #2255aa, активная цифра #ff8800
  wsrgb.py --ws red green blue
                              базовый белый; у активной цифры цвет из палитры
                              по номеру стола: ws1=red, ws2=green, ws3=blue,
                              дальше цвета циклически повторяются
  wsrgb.py --off              погасить всю клавиатуру и выйти
  wsrgb.py -h, --help         показать эту справку

Если --ws не задан, активная цифра красится циклическим оттенком.
Базовый цвет по умолчанию — белый.
Важно: одновременно с wsrgb держать только ОДИН процесс, пишущий в устройство
(или server.py, или wsrgb).
"""

HELP = __doc__
import json
import os
import select
import socket
import subprocess
import sys
import time

import msikb as K

DIGIT_LEDS = [0x1e, 0x1f, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27]
SOCK2 = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                     "hypr", os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", ""), ".socket2.sock")


def active_ws():
    try:
        out = subprocess.check_output(["hyprctl", "activeworkspace", "-j"], text=True, timeout=2)
        return int(json.loads(out)["id"])
    except Exception:
        return None


def apply(kb, ws, base, ws_colors):
    hi = (ws - 1) % len(DIGIT_LEDS) if ws is not None else None
    frame = {}
    for i, led in enumerate(DIGIT_LEDS):
        if i == hi:
            frame[led] = ws_colors[i % len(ws_colors)] if ws_colors else K.hsv(hi / len(DIGIT_LEDS), 0.85, 1.0)
        else:
            frame[led] = base
    for led in K.all_leds():
        if led not in DIGIT_LEDS:
            frame[led] = base
    K.send_colors(kb, frame, order=K.all_leds())


def main():
    args = sys.argv[1:]
    base = (255, 255, 255)
    ws_colors = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            print(HELP, end="")
            return
        elif a == "--base":
            base = K.parse_color(args[i + 1])
            i += 2
        elif a == "--ws":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                ws_colors.append(K.parse_color(args[i]))
                i += 1
        elif a == "--off":
            kb = K.LibUSB()
            try:
                K.send_colors(kb, {l: (0, 0, 0) for l in K.all_leds()}, order=K.all_leds())
            finally:
                kb.close()
            return
        else:
            print(f"unknown argument: {a}", file=sys.stderr)
            print(HELP, end="", file=sys.stderr)
            return

    kb = K.LibUSB()
    last = None
    synced = 0.0
    try:
        sock = None
        if os.path.exists(SOCK2):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(SOCK2)
            sock.setblocking(False)
        while True:
            now = time.time()
            if now - synced > 3:
                ws = active_ws()
                synced = now
                if ws != last:
                    last = ws
                    apply(kb, ws, base, ws_colors)
            if sock:
                r, _, _ = select.select([sock], [], [], 1.0)
                if r:
                    try:
                        data = sock.recv(4096).decode(errors="ignore")
                    except OSError:
                        data = ""
                    for line in data.splitlines():
                        if line.startswith("workspacev2>>"):
                            try:
                                ws = int(line.split(">>")[1].split(",")[0])
                            except ValueError:
                                continue
                            if ws != last:
                                last = ws
                                apply(kb, ws, base, ws_colors)
            else:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            K.send_colors(kb, {l: (0, 0, 0) for l in K.all_leds()}, order=K.all_leds())
        except Exception:
            pass
        kb.close()


if __name__ == "__main__":
    main()
