#!/usr/bin/env python3
"""
mp3srv.py – serve *.mp3 files with a tiny web player
Usage:
    python3 mp3srv.py [root] [--port PORT]
"""
import os, sys, argparse, http.server, json, urllib.parse, socketserver

# ---------- CLI ----------
ap = argparse.ArgumentParser(description="Serve *.mp3 files with a web player")
ap.add_argument("root", nargs="?", default=".", help="directory to serve (default: current dir)")
ap.add_argument("--port", type=int, default=8000, help="listen port (default: 8000)")
args = ap.parse_args()

ROOT = os.path.abspath(args.root)
PORT = args.port
AUDIO_EXT = '.mp3'

if not os.path.isdir(ROOT):
    sys.exit(f"Error: {ROOT} is not a directory")

os.chdir(ROOT)

# ---------- server ----------
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.unquote(self.path.split('?', 1)[0])
        if path == '/playlist.json':
            files = [f for f in os.listdir('.') if f.lower().endswith(AUDIO_EXT)]
            self.send_json(files)
            return
        if path == '/':
            self.send_html(PLAYER_HTML)
            return
        super().do_GET()

    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def send_json(self, obj):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

# ---------- tiny player ----------
PLAYER_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>mp3srv + real-time EQ</title>
<style>
  body{font-family:sans-serif;text-align:center;margin:0;background:#111;color:#eee}
  #now{margin:8px 0;font-weight:bold}
  button{width:4.5em;height:2.2em;margin:.2em;font-size:1em}
  #a{display:none}
  #eq{display:flex;justify-content:center;align-items:end;height:120px;margin:10px 0}
  .bar{width:6px;margin:1px;background:#0f0;min-height:2px}
  #controls{margin:10px auto;width:320px;display:flex;flex-direction:column}
  .band{display:flex;justify-content:space-between;align-items:center;margin:3px 0}
  .band input{width:200px}
</style>
</head>
<body>
  <div id="now">loading…</div>

  <audio id="a" preload="metadata"></audio>

  <!-- spectrum visualizer -->
  <div id="eq"></div>

  <!-- EQ sliders -->
  <div id="controls"></div>

  <!-- transport -->
  <button onclick="prev()">⏮</button>
  <button onclick="toggle()">⏯</button>
  <button onclick="next()">⏭</button>

<script>
/* ---------- playlist ---------- */
let idx = 0, list = [];
const a   = document.getElementById('a');
const now = document.getElementById('now');

fetch('/playlist.json')
  .then(r => r.json())
  .then(files => {
      list = files;
      if (list.length) { setupEQ(); load(0); }
      else now.textContent = 'No mp3 files found.';
  });

/* ---------- Web Audio setup ---------- */
let ctx, source, analyser, bands=[], gains=[];

function setupEQ(){
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  source = ctx.createMediaElementSource(a);

  /* 10 octave-spaced bands (approx) */
  const freqs = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
  freqs.forEach((f,i)=>{
    const filter = ctx.createBiquadFilter();
    filter.type = 'peaking';
    filter.frequency.value = f;
    filter.Q.value  = Math.SQRT2;          // ≈ 1.41
    filter.gain.value = 0;                 // flat
    bands.push(filter);
    gains.push(filter.gain);

    /* UI slider */
    const row = document.createElement('div');
    row.className = 'band';
    row.innerHTML = `
      <label>${f} Hz</label>
      <input type="range" min="-12" max="12" value="0" step="0.5">
      <span>0 dB</span>`;
    const slider = row.querySelector('input');
    const span   = row.querySelector('span');
    slider.addEventListener('input', e=>{
      const g = parseFloat(e.target.value);
      gains[i].value = g;
      span.textContent = g + ' dB';
    });
    document.getElementById('controls').appendChild(row);
  });

  /* chain: source → filters → analyser → destination */
  let node = source;
  bands.forEach(b=>{ node.connect(b); node = b; });
  analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  node.connect(analyser).connect(ctx.destination);

  /* spectrum visualizer */
  const bufferLength = analyser.frequencyBinCount;
  const dataArray    = new Uint8Array(bufferLength);
  const eqDiv        = document.getElementById('eq');
  for (let i=0;i<64;i++){
    const bar = document.createElement('div');
    bar.className = 'bar';
    eqDiv.appendChild(bar);
  }
  const bars = eqDiv.children;
  function draw(){
    analyser.getByteFrequencyData(dataArray);
    for (let i=0;i<bars.length;i++){
      const h = dataArray[i*4];
      bars[i].style.height = (h/2) + 'px';
    }
    requestAnimationFrame(draw);
  }
  draw();
}

/* ---------- player helpers ---------- */
function load(i){
  idx = (i + list.length) % list.length;
  now.textContent = `Now playing: ${list[idx]}`;
  a.src = encodeURIComponent(list[idx]);
  a.play();
}
function next(){load(idx+1);}
function prev(){load(idx-1);}
function toggle(){
  if (ctx.state === 'suspended') ctx.resume();
  a.paused ? a.play() : a.pause();
}
a.addEventListener('ended', next);
</script>
</body>
</html>"""

# ---------- run ----------
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving *.mp3 from {ROOT} on http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
