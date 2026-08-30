#!/usr/bin/env python3
"""Web UI for MSI SteelSeries KLC per-key backlight.

  python3 server.py [port]        default port 8765, then open http://localhost:8765
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import msikb as K

CONFIG = {"mode": "static", "colors": {}, "speed": 1.0}
CONFIG_LOCK = threading.Lock()
PROBE = {"active": False, "led": 0, "color": "#ff0000"}


def renderer():
    kb = K.LibUSB()
    last_frame = None
    try:
        while True:
            with CONFIG_LOCK:
                cfg = dict(CONFIG)
            if PROBE["active"]:
                t = time.time()
                onoff = int(t * 4) % 2 == 0
                if onoff:
                    K.light_one(kb, PROBE["led"], K.parse_color(PROBE["color"]))
                else:
                    K.send_colors(kb, {led: (0, 0, 0) for led in K.all_leds()}, order=K.all_leds())
                time.sleep(0.12)
                continue
            mode = cfg.get("mode", "static")
            frame = K.render_frame(cfg, time.time())
            if mode in ("static", "off"):
                fkey = json.dumps(frame, sort_keys=True)
                if fkey == last_frame:
                    time.sleep(0.15)
                    continue
                last_frame = fkey
                K.send_colors(kb, frame)
                time.sleep(0.1)
            else:
                last_frame = None
                K.send_colors(kb, frame)
                time.sleep(1.0 / 25)
    except Exception as e:
        raise SystemExit(f"renderer failed: {e}")
    finally:
        kb.close()


def layout_payload():
    efm = K.effective_map()
    rows = []
    for row in K.ROWS:
        rows.append([{"id": n, "label": n, "led": efm[n],
                      "w": K.WIDTHS.get(n, 1.0)} for n in row])
    nav = []
    for col in K.NAV:
        nav.append([{"id": n, "label": n, "led": efm[n]} for n in col])
    arrows = [{"id": n, "label": n, "led": efm[n]} for n in K.ARROWS]
    return {"rows": rows, "nav": nav, "arrows": arrows}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = INDEX_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/layout":
            self._json(layout_payload())
        elif self.path == "/api/config":
            with CONFIG_LOCK:
                self._json(CONFIG)
        elif self.path == "/api/state":
            with CONFIG_LOCK:
                self._json({"config": CONFIG, "probe": PROBE})
        else:
            self.send_error(404)

    def do_POST(self):
        data = self._read()
        if self.path == "/api/config":
            with CONFIG_LOCK:
                if "mode" in data:
                    CONFIG["mode"] = data["mode"]
                if "colors" in data:
                    CONFIG["colors"] = {str(int(k)): v for k, v in data["colors"].items()}
                if "speed" in data:
                    CONFIG["speed"] = float(data["speed"])
                self._json(CONFIG)
        elif self.path == "/api/keymap":
            # {"id": "home", "led": 74} — remap a key to a specific LED index
            overrides = K.load_keymap()
            overrides[data["id"]] = int(data["led"])
            K.save_keymap(overrides)
            self._json({"ok": True, "id": data["id"], "led": int(data["led"])})
        elif self.path == "/api/probe":
            PROBE["active"] = data.get("active", False)
            if "led" in data:
                PROBE["led"] = int(data["led"])
            if "color" in data:
                PROBE["color"] = data["color"]
            self._json(dict(PROBE))
        else:
            self.send_error(404)


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MSI KLC — подсветка</title>
<style>
:root { --bg:#15171c; --panel:#1e2228; --key:#232830; --key-edge:#0c0e12; --txt:#d7dbe2; --acc:#e04452; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--txt); font:15px/1.3 system-ui, sans-serif; padding:18px; }
h1 { font-size:18px; font-weight:600; margin-bottom:14px; color:#fff; }
h1 b { color:var(--acc); }
.panels { display:flex; gap:16px; flex-wrap:wrap; }
#kbd { background:var(--panel); border-radius:10px; padding:14px; box-shadow:0 4px 18px #00000066; }
.row { display:flex; gap:4px; margin-bottom:4px; }
.key { --w:1; --h:1; display:flex; flex:0 0 auto; width:calc(var(--w)*42px); height:40px;
  margin:2px; border-radius:6px; background:radial-gradient(120% 120% at 50% 20%, #2d333c, #1a1e24);
  border:1px solid var(--key-edge); align-items:center; justify-content:center; font-size:11px;
  color:#9aa3af; user-select:none; cursor:pointer; transition:transform .05s, box-shadow .15s, background .15s; }
.key:hover { transform:translateY(-1px); }
.key.on { color:#0a0c10; font-weight:700; }
.key.paint { box-shadow:0 0 0 2px var(--bg), 0 0 18px currentColor inset; }
.right { display:flex; gap:6px; margin-left:10px; }
.navcol { display:flex; flex-direction:column; gap:4px; }
.navwrap { display:flex; gap:4px; }
.arrows { display:flex; flex-direction:column; gap:4px; margin-left:10px; align-self:center; }
.arrows .key { width:42px; }
.arrowrow { display:flex; gap:4px; }
.sidebar { background:var(--panel); border-radius:10px; padding:14px; width:260px; }
.group { margin-bottom:16px; }
label { display:block; font-size:12px; color:#8a93a0; margin-bottom:6px; text-transform:uppercase; letter-spacing:.05em; }
.swatches { display:grid; grid-template-columns:repeat(6, 30px); gap:8px; }
.sw { width:30px; height:30px; border-radius:8px; cursor:pointer; border:2px solid transparent; }
.sw.cur { border-color:#fff; }
.hexrow { display:flex; gap:8px; margin-top:10px; }
#hex { width:110px; background:#0f1115; border:1px solid #333b45; color:var(--txt);
  border-radius:6px; padding:7px 8px; font-family:ui-monospace, monospace; }
input[type=color] { width:42px; height:32px; border:none; background:none; cursor:pointer; }
input[type=range] { width:100%; accent-color:var(--acc); cursor:pointer; }
.modes { display:flex; flex-wrap:wrap; gap:6px; }
.btn { padding:7px 10px; border-radius:6px; border:1px solid #333b45; background:#232830; color:var(--txt);
  cursor:pointer; font-size:13px; }
.btn:hover { background:#2c323b; }
.btn.on { background:var(--acc); border-color:var(--acc); color:#fff; font-weight:700; }
.btn.apply { width:100%; background:var(--acc); border-color:var(--acc); color:#fff; font-weight:700; padding:10px; }
.tip { font-size:12px; color:#8a93a0; margin-top:6px; line-height:1.5; }
#msg { position:fixed; bottom:14px; right:14px; background:#2b2222; color:#ffb4b4; padding:10px 14px;
  border-radius:8px; font-size:13px; opacity:0; transition:opacity .2s; pointer-events:none; }
.probediv { margin-top:8px; display:none; }
.probediv.show { display:block; }
.idrow { display:flex; gap:6px; align-items:center; }
#stk { width:70px; font-family:ui-monospace, monospace; }
</style>
</head>
<body>
<h1>MSI GS65 <b>KLC</b> подсветка — по клавишам</h1>
<div class="panels">
  <div id="kbd"></div>
  <div class="sidebar">
    <div class="group">
      <label>Цвет</label>
      <div class="swatches" id="swatches"></div>
      <div class="hexrow">
        <input id="hex" spellcheck="false" value="#ff0044">
        <input type="color" id="colorpick">
      </div>
      <div style="margin-top:10px">
        <label>Яркость <span id="brv">100%</span></label>
        <input type="range" id="br" min="0" max="100" value="100">
      </div>
    </div>
    <div class="group">
      <label>Режим</label>
      <div class="modes" id="modes">
        <button class="btn on" data-mode="static">Рисование</button>
        <button class="btn" data-mode="rainbow">Радуга</button>
        <button class="btn" data-mode="wave">Волна</button>
        <button class="btn" data-mode="breathe">Дыхание</button>
        <button class="btn" data-mode="starlight">Звёзды</button>
        <button class="btn" data-mode="off">Выкл</button>
      </div>
      <div style="margin-top:10px">
        <label>Скорость</label>
        <input type="range" id="spd" min="0.1" max="3" step="0.1" value="1">
      </div>
    </div>
    <button class="btn apply" id="apply">Применить</button>
    <div class="group" style="margin-top:16px">
      <label>Поиск клавиши</label>
      <button class="btn" id="idbtn">Режим поиска</button>
      <div class="probediv" id="probediv">
        <div class="idrow" style="margin-top:8px">
          <button class="btn" id="prev">&larr;</button>
          <input id="stk" value="0x4a">
          <button class="btn" id="next">&rarr;</button>
        </div>
        <button class="btn" id="idsave" style="width:100%;margin-top:6px">Сохранить индекс для клавиши</button>
        <div id="stkey"></div>
      </div>
    </div>
    <div class="tip">ЛКМ — закрасить, ПКМ — стереть, перетаскивание красит непрерывно.<br>
      В режиме поиска кликните клавишу: она начнёт мигать; стрелками подберите нужный LED-индекс и сохраните.</div>
  </div>
</div>
<div id="msg"></div>
<script>
let MODE = "static", COLORS = {}, SPEED = 1, BRIGHT = 1, CUR = "#ff0044";
let PROBING = false, PROBE_KEY = null, PROBE_IDX = null;
let painting = false;
const $ = id => document.getElementById(id);

function msg(s){ const m=$("msg"); m.textContent=s; m.style.opacity=1; setTimeout(()=>m.style.opacity=0, 2200); }
const hexToRgb = h => { h=h.replace("#",""); return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)]; };
const rgbToHex = (a,b,c) => "#"+[a,b,c].map(v=>Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,"0")).join("");
function CURRGB(){ const c=hexToRgb(CUR); const bb=v=>(v*BRIGHT)|0; return [bb(c[0]),bb(c[1]),bb(c[2])]; }

function setKey(d, rgb){
  if (rgb===null){
    COLORS[d.dataset.led]=null;
    d.classList.remove("on","paint"); d.style.background=""; d.style.color=""; d.style.boxShadow="";
  } else {
    const s = rgbToHex(...rgb);
    COLORS[d.dataset.led]=s;
    d.classList.add("on","paint");
    d.style.background=s; d.style.color="#fff"; d.style.boxShadow=`0 0 14px ${s}`;
  }
}

function makeKey(id, label, led, w){
  const d = document.createElement("div");
  d.className = "key";
  d.dataset.keyid = id; d.dataset.led = led;
  if (w) d.style.width = (w*42)+"px";
  d.textContent = label;
  d.addEventListener("mousedown", e => {
    e.preventDefault();
    if (PROBING){ startProbe(d); return; }
    if (e.button===2){ setKey(d, null); painting=false; }
    else { setKey(d, CURRGB()); painting=true; }
  });
  d.addEventListener("mouseenter", () => { if (painting && !PROBING) setKey(d, CURRGB()); });
  d.addEventListener("contextmenu", e => e.preventDefault());
  return d;
}

function build(l){
  const kbd = $("kbd"); kbd.innerHTML="";
  const main = document.createElement("div");
  l.rows.forEach(row => {
    const r = document.createElement("div"); r.className="row";
    row.forEach(k => r.appendChild(makeKey(k.id, k.id, k.led, k.w)));
    main.appendChild(r);
  });
  const right = document.createElement("div"); right.className="right";
  const navwrap = document.createElement("div"); navwrap.className="navwrap";
  l.nav.forEach(col => {
    const c = document.createElement("div"); c.className="navcol";
    col.forEach(k => c.appendChild(makeKey(k.id, k.id, k.led)));
    navwrap.appendChild(c);
  });
  right.appendChild(navwrap);
  const glyph = {"up":"\u2191","left":"\u2190","down":"\u2193","right":"\u2192"};
  const ar = document.createElement("div"); ar.className="arrows";
  const up = makeKey(l.arrows[0].id, glyph[l.arrows[0].id]||l.arrows[0].id, l.arrows[0].led); ar.appendChild(up);
  const arow = document.createElement("div"); arow.className="arrowrow";
  l.arrows.slice(1).forEach(k => arow.appendChild(makeKey(k.id, glyph[k.id]||k.id, k.led)));
  ar.appendChild(arow);
  right.appendChild(ar);
  kbd.appendChild(main); kbd.appendChild(right);
}

document.querySelectorAll("#modes .btn").forEach(b => b.onclick = () => {
  MODE = b.dataset.mode;
  document.querySelectorAll("#modes .btn").forEach(x => x.classList.toggle("on", x===b));
});

const SW = ["#ff0044","#ff7700","#ffdd00","#00ff66","#00ccff","#0066ff","#aa00ff","#ff00aa",
            "#ffffff","#ff4040","#40ff40","#4444ff","#000000","#ff8800","#00ffaa","#ff4488"];
const sw = $("swatches");
const setCur = h => { CUR=h; $("hex").value=h; $("colorpick").value=h;
  sw.querySelectorAll(".sw").forEach(x=>x.classList.toggle("cur", x.dataset.c==h)); };
SW.forEach((h,i) => {
  const s = document.createElement("div"); s.className="sw"; s.dataset.c=h; s.style.background=h;
  if (i===0) s.classList.add("cur");
  s.onclick = () => setCur(h);
  sw.appendChild(s);
});
$("hex").oninput = e => { const v="#"+e.target.value.replace(/[^0-9a-fA-F]/g,"").slice(0,6); CUR=v; };
$("colorpick").oninput = e => { CUR=e.target.value; $("hex").value=CUR; };
$("br").oninput = e => { BRIGHT=e.target.value/100; $("brv").textContent=Math.round(BRIGHT*100)+"%"; };
$("spd").oninput = e => { SPEED=parseFloat(e.target.value); };

async function api(path, method, body){
  const r = await fetch(path, { method, headers: body?{"Content-Type":"application/json"}:undefined,
    body: body?JSON.stringify(body):undefined });
  return r.json();
}

$("apply").onclick = async () => {
  if (PROBING) stopProbe();
  const colors = {};
  Object.entries(COLORS).forEach(([led,c]) => { if (c) colors[led]=c; });
  await api("/api/config", "POST", { mode: MODE, colors, speed: SPEED });
  msg("применено · режим " + MODE);
};

function startProbe(d){
  PROBING=true; PROBE_KEY=d.dataset.keyid; PROBE_IDX=parseInt(d.dataset.led);
  $("probediv").classList.add("show");
  $("stkey").textContent = "Клавиша: " + PROBE_KEY;
  $("stk").value = "0x"+PROBE_IDX.toString(16);
  api("/api/probe","POST",{active:true, led:PROBE_IDX, color:CUR});
}
function stopProbe(){
  PROBING=false; PROBE_IDX=null; PROBE_KEY=null;
  $("probediv").classList.remove("show");
  api("/api/probe","POST",{active:false});
}
function stepProbe(delta){
  if (PROBE_IDX===null) return;
  PROBE_IDX = Math.max(0, PROBE_IDX+delta);
  $("stk").value = "0x"+PROBE_IDX.toString(16);
  api("/api/probe","POST",{active:true, led:PROBE_IDX, color:CUR});
}
$("idbtn").onclick = () => { if (PROBING) stopProbe(); else msg("Кликните по клавише — она начнёт мигать"); };
$("prev").onclick = () => stepProbe(-1);
$("next").onclick = () => stepProbe(1);
$("idsave").onclick = async () => {
  if (PROBE_KEY==null) return;
  await api("/api/keymap","POST",{id:PROBE_KEY, led:PROBE_IDX});
  api("/api/probe","POST",{active:false});
  PROBING=false; $("probediv").classList.remove("show");
  msg("Сохранено: "+PROBE_KEY+" = 0x"+PROBE_IDX.toString(16));
  const l = await api("/api/layout","GET"); build(l);
};

(function init(){
  api("/api/layout","GET").then(build);
  window.addEventListener("mouseup", ()=> painting=false);
})();
</script>
</body>
</html>
"""


def main():
    port = 8765
    import sys as _sys
    if len(_sys.argv) > 1:
        port = int(_sys.argv[1])
    threading.Thread(target=renderer, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"MSI KLC web UI: http://localhost:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()