"""Visual replay dashboard (Story 3.4, FR17 / UX-DR1).

Replays a crisis fixture: the fragility score climbs through RED *before* the cascade
block, with a live RCS panel naming the epicenter protocols. Self-contained (no external
CDN) so it runs offline. CPU-only. The UI lets you switch crisis, change replay speed,
pause and scrub.

    python3 -m demo.dashboard                 # http://localhost:8080
    python3 -m demo.dashboard --fixture ftx_2022_11_08
"""
import argparse
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores, rcs_scores
from engine.scoring import score_100, FIT_WINDOW
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block
from tools.extract_fixtures import FIXTURES, UNI_POOLS, COMPOUND, AAVE_V2, AAVE_V3, SPARK
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")

_LABELS = {a: f"{t0}/{t1}" for a, t0, t1 in UNI_POOLS}
_LABELS.update({a: f"c{u}" for a, u in COMPOUND})
_LABELS.update({AAVE_V2: "AaveV2", AAVE_V3: "AaveV3", SPARK: "Spark"})


def _label(addr):
    return _LABELS.get(addr, addr[:10])


def _available_fixtures():
    names = sorted(p.name[:-7] for p in FIXTURE_DIR.glob("*.csv.gz"))
    return [{"name": n, "category": CATEGORY.get(n, "custom")} for n in names]


@lru_cache(maxsize=16)
def build_timeline(fixture):
    """Precompute score + RCS per scored window for a fixture."""
    path = FIXTURE_DIR / f"{fixture}.csv.gz"
    if not path.exists():
        return {"error": f"fixture not extracted: {fixture}"}
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return {"error": "fixture too sparse"}

    ends = window_end_blocks(events)
    points = []
    for i, raw in enumerate(rolling_scores(R, fit_window=FIT_WINDOW)):
        s = round(score_100(raw), 2)
        blk = scored_index_to_block(ends, i)
        rcs_top = []
        if s >= 50:
            window = R[:, i:i + FIT_WINDOW]
            rcs = rcs_scores(window, contracts)
            rcs_top = [{"contract": _label(c), "contribution": round(float(v), 4)}
                       for c, v in list(rcs.items())[:3]]
        level = "RED" if s >= 90 else ("YELLOW" if s >= 70 else None)
        points.append({"block": blk, "score": s, "level": level, "rcs": rcs_top})

    return {
        "fixture": fixture,
        "cascade_block": FIXTURES[fixture][2] if fixture in FIXTURES else None,
        "thresholds": {"yellow": 70, "red": 90},
        "points": points,
    }


def create_app(default_fixture="luna_2022_05_09"):
    app = FastAPI(title="QuantumRadar Dashboard")

    @app.get("/api/fixtures")
    def fixtures():
        return {"fixtures": _available_fixtures(), "default": default_fixture}

    @app.get("/api/timeline")
    def timeline(fixture: str = default_fixture):
        return build_timeline(fixture)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _HTML

    return app


_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>QuantumRadar</title><style>
body{margin:0;background:#0b0f1a;color:#e6edf3;font-family:ui-monospace,Menlo,monospace}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 4px}.sub{color:#8b949e;font-size:13px;margin-bottom:12px}
.ctrls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
select,.btn{background:#1f2937;border:1px solid #374151;color:#e6edf3;border-radius:6px;padding:6px 10px;font-family:inherit;cursor:pointer}
.btn.active{background:#1f6feb;border-color:#1f6feb}
.row{display:flex;gap:20px}.card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:16px}
#chart{flex:1}canvas{width:100%;height:340px}
.score{font-size:54px;font-weight:700;line-height:1}.lvl{font-size:14px;letter-spacing:2px}
.panel{width:280px}.rcs div{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1f2937;font-size:13px}
.red{color:#ff4d4f}.yellow{color:#f5c542}.green{color:#3fb950}
input[type=range]{width:100%}
</style></head><body><div class="wrap">
<h1>QuantumRadar — systemic fragility replay</h1>
<div class="sub" id="meta">loading…</div>
<div class="ctrls">
  <label>crisis</label><select id="fx"></select>
  <button class="btn" id="play">▶ play</button>
  <label style="margin-left:8px">speed</label>
  <span id="speeds"></span>
</div>
<input type="range" id="scrub" min="0" max="0" value="0" style="margin-bottom:14px">
<div class="row">
 <div class="card" id="chart"><canvas id="cv"></canvas></div>
 <div class="card panel">
   <div class="lvl" id="lvl">—</div><div class="score" id="score">0</div>
   <div style="color:#8b949e;font-size:12px;margin:6px 0 12px" id="blk"></div>
   <div style="font-size:12px;color:#8b949e">RCS — epicenter</div>
   <div class="rcs" id="rcs"></div>
 </div>
</div></div>
<script>
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
let T=null,playhead=0,timer=null,playing=false,speedMs=80;
const SPEEDS=[[160,'0.5x'],[80,'1x'],[40,'2x'],[20,'4x']];
function fit(){cv.width=cv.clientWidth*devicePixelRatio;cv.height=340*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);}
function draw(){const W=cv.clientWidth,H=340,pts=T.points;ctx.clearRect(0,0,W,H);
 const b0=pts[0].block,b1=pts[pts.length-1].block,x=b=>(b-b0)/(b1-b0||1)*(W-50)+40,y=s=>H-20-(s/100)*(H-40);
 [[70,'#f5c542'],[90,'#ff4d4f']].forEach(([t,c])=>{ctx.strokeStyle=c;ctx.globalAlpha=.4;ctx.beginPath();ctx.moveTo(40,y(t));ctx.lineTo(W-10,y(t));ctx.stroke();ctx.globalAlpha=1;});
 if(T.cascade_block){const cx=x(T.cascade_block);ctx.strokeStyle='#8b949e';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(cx,10);ctx.lineTo(cx,H-20);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#8b949e';ctx.font='11px monospace';ctx.fillText('cascade',cx-20,20);}
 ctx.beginPath();ctx.strokeStyle='#58a6ff';ctx.lineWidth=2;
 pts.slice(0,playhead+1).forEach((p,i)=>{const X=x(p.block),Y=y(p.score);i?ctx.lineTo(X,Y):ctx.moveTo(X,Y);});ctx.stroke();
 const p=pts[playhead];if(p){ctx.fillStyle=p.level==='RED'?'#ff4d4f':p.level==='YELLOW'?'#f5c542':'#58a6ff';ctx.beginPath();ctx.arc(x(p.block),y(p.score),4,0,7);ctx.fill();}}
function render(){const p=T.points[playhead];document.getElementById('score').textContent=p.score.toFixed(1);
 const l=document.getElementById('lvl');l.textContent=p.level||'CALM';l.className='lvl '+(p.level==='RED'?'red':p.level==='YELLOW'?'yellow':'green');
 document.getElementById('score').className='score '+(p.level==='RED'?'red':p.level==='YELLOW'?'yellow':'');
 document.getElementById('blk').textContent='block '+p.block;
 document.getElementById('scrub').value=playhead;
 document.getElementById('rcs').innerHTML=(p.rcs||[]).map(r=>`<div><span>${r.contract}</span><span>${r.contribution}</span></div>`).join('')||'<div style="color:#8b949e">—</div>';
 draw();}
function stop(){playing=false;clearInterval(timer);document.getElementById('play').textContent='▶ play';}
function tick(){if(playhead>=T.points.length-1){stop();return;}playhead++;render();}
function play(){if(playing){stop();return;}if(playhead>=T.points.length-1)playhead=0;
 playing=true;document.getElementById('play').textContent='⏸ pause';clearInterval(timer);timer=setInterval(tick,speedMs);}
function setSpeed(ms){speedMs=ms;document.querySelectorAll('#speeds .btn').forEach(b=>b.classList.toggle('active',+b.dataset.ms===ms));if(playing){clearInterval(timer);timer=setInterval(tick,speedMs);}}
function loadTimeline(fx){stop();fetch('/api/timeline?fixture='+encodeURIComponent(fx)).then(r=>r.json()).then(d=>{
 if(d.error){document.getElementById('meta').textContent=d.error;return;}
 T=d;fit();playhead=T.points.length-1;
 document.getElementById('scrub').max=T.points.length-1;
 const casc=d.cascade_block?` · cascade @ ${d.cascade_block}`:'';
 document.getElementById('meta').textContent=`${d.fixture} · ${d.points.length} windows · YELLOW 70 / RED 90${casc}`;
 render();});}
document.getElementById('play').onclick=play;
document.getElementById('scrub').oninput=e=>{stop();playhead=+e.target.value;render();};
const sp=document.getElementById('speeds');SPEEDS.forEach(([ms,lbl])=>{const b=document.createElement('button');b.className='btn'+(ms===80?' active':'');b.textContent=lbl;b.dataset.ms=ms;b.onclick=()=>setSpeed(ms);sp.appendChild(b);});
fetch('/api/fixtures').then(r=>r.json()).then(d=>{const sel=document.getElementById('fx');
 d.fixtures.forEach(f=>{const o=document.createElement('option');o.value=f.name;o.textContent=`${f.name}  [${f.category}]`;sel.appendChild(o);});
 sel.value=d.default;sel.onchange=()=>loadTimeline(sel.value);loadTimeline(d.default);});
window.addEventListener('resize',()=>{if(T){fit();render();}});
</script></body></html>"""


app = create_app()


def main(argv=None):
    ap = argparse.ArgumentParser(description="QuantumRadar dashboard")
    ap.add_argument("--fixture", default="luna_2022_05_09")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args(argv)
    import uvicorn
    uvicorn.run(create_app(args.fixture), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
