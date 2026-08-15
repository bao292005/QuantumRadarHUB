"""Visual replay dashboard (Story 3.4, FR17 / UX-DR1) — TradingView-style.

ETH candlesticks with a zoom/pan viewport (wheel = zoom, drag = pan, dbl-click = fit),
so a multi-month span with thousands of candles stays readable. Below: a FRAGILITY
oscillator with shaded RED/YELLOW alert bands + B0 baseline, a LIQUIDATIONS histogram,
a lead-time hero callout, red screen pulse, a live alert FEED, and the honest
out-of-sample F1 (CFI+MPS vs B0). Self-contained (no external CDN), CPU-only.

    python3 -m demo.dashboard                 # http://localhost:8080
    python3 -m demo.dashboard --fixture ftx_2022_11_08
"""
import argparse
import bisect
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores, rcs_scores
from engine.scoring import score_100, FIT_WINDOW, WINDOW_BLOCKS, STRIDE_BLOCKS
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block, SECONDS_PER_BLOCK
from tools.price import window_ohlc
from tools.baselines import b0_scores
from tools.extract_fixtures import FIXTURES, UNI_POOLS, COMPOUND, AAVE_V2, AAVE_V3, SPARK
from tools.honest_detection_count import CATEGORY
from tools.f1_backtest import compute_f1

FIXTURE_DIR = Path("fixtures/backtest")

_LABELS = {a: f"{t0}/{t1}" for a, t0, t1 in UNI_POOLS}
_LABELS.update({a: f"c{u}" for a, u in COMPOUND})
_LABELS.update({AAVE_V2: "AaveV2", AAVE_V3: "AaveV3", SPARK: "Spark"})

_NAMES = {
    "luna_2022_05_09": "LUNA / UST collapse",
    "ftx_2022_11_08": "FTX collapse week",
    "steth_depeg_2022_06": "stETH depeg",
    "may_2021_eth_crash": "May 2021 ETH crash",
    "wbtc_cascade_2022_06": "WBTC deleverage cascade",
    "eth_cascade_ftx_week_2022_11": "ETH cascade (FTX week)",
    "usdc_depeg_2023_03": "USDC / SVB depeg",
    "busd_freeze_2023_02": "BUSD freeze",
    "euler_hack_2023_03": "Euler exploit",
    "normal_2023_03_15": "Normal market",
    "crv_near_miss_2023_08": "CRV near-miss (Aug)",
    "crv_near_miss_2023_11": "CRV near-miss (Nov)",
}


def _label(addr):
    return _LABELS.get(addr, addr[:10])


def _available_fixtures():
    names = sorted(p.name[:-7] for p in FIXTURE_DIR.glob("*.csv.gz"))
    return [{"name": n, "category": CATEGORY.get(n, "custom")} for n in names]


def _liq_per_window(events):
    blocks = [e["block_number"] for e in events]
    if not blocks:
        return []
    lo, hi = blocks[0], blocks[-1]
    out, b = [], lo + WINDOW_BLOCKS
    while b <= hi:
        li = bisect.bisect_left(blocks, b - WINDOW_BLOCKS)
        ri = bisect.bisect_right(blocks, b)
        out.append(sum(1 for e in events[li:ri] if e.get("event_type") == "liquidation"))
        b += STRIDE_BLOCKS
    return out


@lru_cache(maxsize=16)
def build_timeline(fixture):
    """Precompute per-window candle (OHLC), fragility, RCS, liquidation, B0."""
    path = FIXTURE_DIR / f"{fixture}.csv.gz"
    if not path.exists():
        return {"error": f"fixture not extracted: {fixture}"}
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return {"error": "fixture too sparse"}

    ends = window_end_blocks(events)
    _, ohlc = window_ohlc(events)
    liq = _liq_per_window(events)
    b0 = b0_scores(events)
    b0_max = max(b0) if b0 else 1.0

    def _at(series, i):
        return series[min(i + FIT_WINDOW, len(series) - 1)] if series else None

    cascade = FIXTURES[fixture][2] if fixture in FIXTURES else None
    points, first_red_block = [], None
    for i, raw in enumerate(rolling_scores(R, fit_window=FIT_WINDOW)):
        s = round(score_100(raw), 2)
        blk = scored_index_to_block(ends, i)
        level = "RED" if s >= 90 else ("YELLOW" if s >= 70 else None)
        if level == "RED" and first_red_block is None and (cascade is None or blk <= cascade):
            first_red_block = blk
        rcs_top = []
        if s >= 50:
            window = R[:, i:i + FIT_WINDOW]
            rcs = rcs_scores(window, contracts)
            rcs_top = [{"contract": _label(c), "contribution": round(float(v), 4)}
                       for c, v in list(rcs.items())[:3]]
        candle = _at(ohlc, i)
        points.append({
            "block": blk, "score": s, "level": level, "rcs": rcs_top,
            "price": candle["c"] if candle else None,
            "ohlc": candle,
            "liq": _at(liq, i) or 0,
            "b0": round(100.0 * (b0[i] / b0_max), 2) if i < len(b0) and b0_max else 0.0,
        })

    lead_h = None
    if cascade is not None and first_red_block is not None:
        lead_h = round((cascade - first_red_block) * SECONDS_PER_BLOCK / 3600.0, 1)

    return {
        "fixture": fixture, "event_name": _NAMES.get(fixture, fixture),
        "category": CATEGORY.get(fixture, "custom"),
        "cascade_block": cascade, "first_red_block": first_red_block, "lead_hours": lead_h,
        "points": points,
    }


@lru_cache(maxsize=8)
def f1_result(fixture):
    """Continuous out-of-sample F1 (CFI+MPS vs B0). Meaningful only for long spans."""
    return compute_f1(fixture)


def create_app(default_fixture="luna_2022_05_09"):
    app = FastAPI(title="QuantumRadar Dashboard")

    @app.get("/api/fixtures")
    def fixtures():
        return {"fixtures": _available_fixtures(), "default": default_fixture}

    @app.get("/api/timeline")
    def timeline(fixture: str = default_fixture):
        return build_timeline(fixture)

    @app.get("/api/f1")
    def f1(fixture: str = default_fixture):
        return f1_result(fixture)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _HTML

    return app


_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>QuantumRadar</title><style>
body{margin:0;background:#0b0f1a;color:#e6edf3;font-family:ui-monospace,Menlo,monospace}
body.red-alert{animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{box-shadow:inset 0 0 0 0 rgba(255,77,79,0)}50%{box-shadow:inset 0 0 90px 0 rgba(255,77,79,.35)}}
.wrap{max-width:1160px;margin:0 auto;padding:20px}
h1{font-size:19px;margin:0 0 10px}
.hero{border-radius:10px;padding:12px 16px;margin-bottom:12px;font-size:17px;background:#111827;border:1px solid #1f2937}
.hero b{font-size:21px}
.ctrls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
select,.btn{background:#1f2937;border:1px solid #374151;color:#e6edf3;border-radius:6px;padding:6px 10px;font-family:inherit;cursor:pointer}
.btn.active{background:#1f6feb;border-color:#1f6feb}
.row{display:flex;gap:16px}.card{background:#0e1420;border:1px solid #1f2937;border-radius:10px;padding:10px}
#chart{flex:1}.plabel{font-size:11px;color:#8b949e;margin:0 0 2px 4px;letter-spacing:.5px}
canvas{width:100%;display:block;cursor:crosshair}
.score{font-size:46px;font-weight:700;line-height:1}.lvl{font-size:13px;letter-spacing:2px}
.panel{width:240px}.rcs div{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1f2937;font-size:12px}
.red{color:#ff4d4f}.yellow{color:#f5c542}.green{color:#3fb950}.muted{color:#8b949e}
input[type=range]{width:100%}
.feed{max-height:200px;overflow:auto;margin-top:6px}.fe{font-size:11px;padding:4px 6px;border-left:3px solid;margin-bottom:3px;background:#111827;border-radius:3px}
.fe.red{border-color:#ff4d4f}.fe.yellow{border-color:#f5c542}
.legend{font-size:11px;color:#8b949e}
.f1t{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}
.f1t th,.f1t td{text-align:left;padding:4px 8px;border-bottom:1px solid #1f2937}
.f1t th{color:#8b949e;font-weight:400}.f1t td:first-child{color:#e6edf3}.win{color:#3fb950;font-weight:700}
</style></head><body><div class="wrap">
<h1>QuantumRadar — systemic fragility replay</h1>
<div class="hero" id="hero">loading…</div>
<div class="ctrls">
  <label>crisis</label><select id="fx"></select>
  <button class="btn" id="play">▶ play</button>
  <label style="margin-left:4px">speed</label><span id="speeds"></span>
  <span style="margin-left:8px"></span>
  <button class="btn" id="zin">＋</button><button class="btn" id="zout">－</button><button class="btn" id="fit">⤢ fit</button>
  <span class="legend" style="margin-left:auto">wheel=zoom · drag=pan · dbl-click=fit</span>
</div>
<input type="range" id="scrub" min="0" max="0" value="0" style="margin-bottom:10px">
<div class="row">
 <div id="chart">
   <div class="card" style="margin-bottom:8px"><div class="plabel">ETH / USDC — candlesticks (alert bands shaded)</div><canvas id="cvC" data-h="230"></canvas></div>
   <div class="card" style="margin-bottom:8px"><div class="plabel">FRAGILITY oscillator — RED&#8805;90 / YELLOW&#8805;70 (+ B0 baseline)</div><canvas id="cvO" data-h="120"></canvas></div>
   <div class="card"><div class="plabel">LIQUIDATIONS per window</div><canvas id="cvL" data-h="90"></canvas></div>
 </div>
 <div class="card panel">
   <div class="lvl" id="lvl">—</div><div class="score" id="score">0</div>
   <div class="muted" style="font-size:12px;margin:6px 0 10px" id="blk"></div>
   <div style="font-size:12px;color:#8b949e">RCS — epicenter</div><div class="rcs" id="rcs"></div>
   <div style="font-size:12px;color:#8b949e;margin-top:12px">ALERT FEED</div><div class="feed" id="feed"></div>
 </div>
</div>
<div class="card" style="margin-top:12px"><div class="plabel">OUT-OF-SAMPLE F1 — continuous backtest · CFI+MPS vs B0 baseline (honest)</div><div id="f1"><span class="muted" style="font-size:12px">—</span></div></div>
</div>
<script>
const dpr=devicePixelRatio||1,PAD=46;
let T=null,playhead=0,timer=null,playing=false,speedMs=80;
let candleW=6,viewStart=0,drag=null,cascadeIdx=-1,firstRedIdx=-1,lastW=900;
const SPEEDS=[[160,'0.5x'],[80,'1x'],[40,'2x'],[20,'4x']];
const $=id=>document.getElementById(id);
function N(){return T.points.length;}
function setup(cv){const h=+cv.dataset.h;cv.style.height=h+'px';cv.width=cv.clientWidth*dpr;cv.height=h*dpr;const c=cv.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);lastW=cv.clientWidth;return{c,W:cv.clientWidth,H:h};}
function visCount(W){return Math.max(1,(W-PAD-8)/candleW);}
function minW(W){return (W-PAD-8)/Math.max(1,N()-1);}
function clampView(W){const maxS=Math.max(0,N()-visCount(W));viewStart=Math.min(Math.max(0,viewStart),maxS);}
function fitAll(W){candleW=minW(W);viewStart=0;}
function xAt(i,W){return PAD+(i-viewStart)*candleW;}
function idxAt(x,W){return viewStart+(x-PAD)/candleW;}
function range(W){return[Math.max(0,Math.floor(viewStart)),Math.min(N()-1,Math.ceil(viewStart+visCount(W)))];}
function scoreColor(l){return l==='RED'?'#ff4d4f':l==='YELLOW'?'#f5c542':'#58a6ff';}
function nearest(b){let bi=0,bd=1e18;T.points.forEach((p,i)=>{const d=Math.abs(p.block-b);if(d<bd){bd=d;bi=i;}});return bi;}
function bands(c,W,H,s,e){for(let i=s;i<=e;i++){const p=T.points[i];if(!p.level)continue;const x=xAt(i,W),w=Math.max(1,candleW);c.fillStyle=p.level==='RED'?'rgba(255,77,79,.13)':'rgba(245,197,66,.10)';c.fillRect(x-w/2,4,w,H-8);}}
function vline(c,idx,W,H,col,txt){if(idx<0)return;const x=xAt(idx,W);if(x<PAD-1||x>W)return;c.strokeStyle=col;c.setLineDash([4,4]);c.beginPath();c.moveTo(x,4);c.lineTo(x,H-4);c.stroke();c.setLineDash([]);if(txt){c.fillStyle=col;c.font='10px monospace';c.fillText(txt,x+2,11);}}
function marks(c,W,H){vline(c,cascadeIdx,W,H,'#8b949e','cascade');vline(c,firstRedIdx,W,H,'#ff8c42','⚠RED');}
function cursor(c,W,H){const x=xAt(playhead,W);if(x<PAD||x>W)return;c.strokeStyle='rgba(230,237,243,.45)';c.beginPath();c.moveTo(x,4);c.lineTo(x,H-4);c.stroke();}
function candles(){const {c,W,H}=setup($('cvC')),p=T.points;c.clearRect(0,0,W,H);const [s,e]=range(W);
 let lo=1e18,hi=-1e18;for(let i=s;i<=e;i++){const o=p[i].ohlc;if(!o)continue;lo=Math.min(lo,o.l);hi=Math.max(hi,o.h);}
 if(lo>hi){lo=0;hi=1;}if(hi===lo)hi=lo+1;const y=v=>H-16-(v-lo)/(hi-lo)*(H-26);
 bands(c,W,H,s,e);marks(c,W,H);const w=Math.max(1,candleW*0.62);
 for(let i=s;i<=e;i++){const o=p[i].ohlc;if(!o)continue;const x=xAt(i,W),up=o.c>=o.o,col=up?'#3fb950':'#ff4d4f';
  c.strokeStyle=col;c.beginPath();c.moveTo(x,y(o.h));c.lineTo(x,y(o.l));c.stroke();
  const yo=y(o.o),yc=y(o.c);c.fillStyle=col;c.fillRect(x-w/2,Math.min(yo,yc),Math.max(1,w),Math.max(1,Math.abs(yc-yo)));}
 cursor(c,W,H);c.fillStyle='#8b949e';c.font='10px monospace';c.fillText('$'+hi.toFixed(0),4,y(hi)+9);c.fillText('$'+lo.toFixed(0),4,y(lo));}
function osc(){const {c,W,H}=setup($('cvO')),p=T.points;c.clearRect(0,0,W,H);const [s,e]=range(W);const y=v=>H-14-(v/100)*(H-22);
 c.fillStyle='rgba(255,77,79,.09)';c.fillRect(PAD,4,W-PAD-8,y(90)-4);c.fillStyle='rgba(245,197,66,.07)';c.fillRect(PAD,y(90),W-PAD-8,y(70)-y(90));
 [[70,'#f5c542'],[90,'#ff4d4f']].forEach(([t,col])=>{c.strokeStyle=col;c.globalAlpha=.5;c.beginPath();c.moveTo(PAD,y(t));c.lineTo(W-8,y(t));c.stroke();c.globalAlpha=1;});
 marks(c,W,H);
 c.strokeStyle='#6e7681';c.setLineDash([5,4]);c.beginPath();let st=false;for(let i=s;i<=e;i++){const X=xAt(i,W),Y=y(p[i].b0);st?c.lineTo(X,Y):c.moveTo(X,Y);st=true;}c.stroke();c.setLineDash([]);
 c.strokeStyle='#58a6ff';c.lineWidth=1.6;c.beginPath();st=false;for(let i=s;i<=e;i++){const X=xAt(i,W),Y=y(p[i].score);st?c.lineTo(X,Y):c.moveTo(X,Y);st=true;}c.stroke();
 cursor(c,W,H);const cur=p[playhead],cx=xAt(playhead,W);if(cx>=PAD&&cx<=W){c.fillStyle=scoreColor(cur.level);c.beginPath();c.arc(cx,y(cur.score),3.2,0,7);c.fill();}
 c.fillStyle='#8b949e';c.font='10px monospace';c.fillText('90',6,y(90)+3);c.fillText('70',6,y(70)+3);}
function hist(){const {c,W,H}=setup($('cvL')),p=T.points;c.clearRect(0,0,W,H);const [s,e]=range(W);
 let hi=1;for(let i=s;i<=e;i++)hi=Math.max(hi,p[i].liq);const y=v=>H-12-(v/hi)*(H-18),w=Math.max(1,candleW*0.62);
 for(let i=s;i<=e;i++){const v=p[i].liq;if(!v)continue;const x=xAt(i,W);c.fillStyle=p[i].level==='RED'?'#ff4d4f':'#ff6b6b';c.fillRect(x-w/2,y(v),Math.max(1,w),H-12-y(v));}
 marks(c,W,H);cursor(c,W,H);c.fillStyle='#8b949e';c.font='10px monospace';c.fillText('max '+hi,6,11);}
function feed(){let out=[],prev=null;for(let i=0;i<=playhead;i++){const p=T.points[i];if(p.level&&p.level!==prev){const r=(p.rcs||[]).map(x=>x.contract).slice(0,2).join(', ');
  out.push(`<div class="fe ${p.level==='RED'?'red':'yellow'}"><b>${p.level}</b> ${p.score.toFixed(0)} · blk ${p.block}${r?' · '+r:''}</div>`);}prev=p.level;}
 return out.reverse().join('')||'<div class="muted" style="font-size:11px">no alerts yet</div>';}
function side(){const p=T.points[playhead];$('score').textContent=p.score.toFixed(1);
 const l=$('lvl');l.textContent=p.level||'CALM';l.className='lvl '+(p.level==='RED'?'red':p.level==='YELLOW'?'yellow':'green');
 $('score').className='score '+(p.level==='RED'?'red':p.level==='YELLOW'?'yellow':'');
 $('blk').innerHTML='block '+p.block+(p.price?` · ETH $${p.price}`:'')+` · ${p.liq} liq`;
 document.body.classList.toggle('red-alert',p.level==='RED');
 $('rcs').innerHTML=(p.rcs||[]).map(r=>`<div><span>${r.contract}</span><span>${r.contribution}</span></div>`).join('')||'<div class="muted">—</div>';
 $('feed').innerHTML=feed();$('scrub').value=playhead;}
function render(){candles();osc();hist();side();}
function hero(){const h=$('hero');
 if(T.lead_hours!=null){h.innerHTML=`🔴 <b>RED fired ${T.lead_hours}h BEFORE cascade</b> — ${T.event_name} <span class="muted">[${T.category}]</span>`;h.style.borderColor='#ff4d4f';}
 else if(T.category==='fp_control'){h.innerHTML=`🟢 <b>${T.event_name}</b> — control, no pre-cascade alert expected <span class="muted">[${T.category}]</span>`;h.style.borderColor='#3fb950';}
 else{h.innerHTML=`<b>${T.event_name}</b> <span class="muted">[${T.category}]</span>`;h.style.borderColor='#1f2937';}}
function renderF1(d){const el=$('f1');
 if(d.error){el.innerHTML=`<span class="muted" style="font-size:12px">${d.error}. F1 cần dải liên tục dài — extract: <code>tools.extract_fixtures --from-block 14700000 --to-block 15010000 --name cont_q2_2022</code></span>`;return;}
 const rows=d.detectors.map(r=>{const w=r.name===d.winner,ci=r.ci?`[${r.ci[0]}, ${r.ci[1]}]`:'—';
   return `<tr><td>${r.name}</td><td class="${w?'win':''}">${r.test_f1}</td><td>${r.precision}</td><td>${r.recall}</td><td>${ci}</td></tr>`;}).join('');
 const honest=d.winner!=='CFI+MPS'
   ?`<div class="yellow" style="font-size:12px;margin-top:8px">⚠ Honest: baseline <b>B0 thắng</b> ở dự báo VOLUME thanh lý (Δ ${d.delta_f1}). CFI+MPS đo cấu trúc tương quan → mạnh ở <b>event-level</b> (7/7, bắt FTX). Xem docs/09.</div>`
   :`<div class="green" style="font-size:12px;margin-top:8px">CFI+MPS ≥ baseline (Δ ${d.delta_f1}).</div>`;
 el.innerHTML=`<div style="font-size:11px;color:#8b949e">span <b>${d.span}</b> · nhãn liquidation-cascade &#8805;P${d.pct} trong ${d.horizon}h · out-of-sample time-split+embargo · TRAIN ${d.train.n} / TEST ${d.test.n}</div>
 <table class="f1t"><tr><th>detector</th><th>test F1</th><th>precision</th><th>recall</th><th>95% CI</th></tr>${rows}</table>${honest}`;}
function stop(){playing=false;clearInterval(timer);$('play').textContent='▶ play';}
function follow(){const W=lastW,x=xAt(playhead,W);if(x<PAD+candleW||x>W-24){viewStart=playhead-visCount(W)*0.5;clampView(W);}}
function tick(){if(playhead>=N()-1){stop();return;}playhead++;follow();render();}
function play(){if(playing){stop();return;}if(playhead>=N()-1)playhead=0;playing=true;$('play').textContent='⏸ pause';clearInterval(timer);timer=setInterval(tick,speedMs);}
function setSpeed(ms){speedMs=ms;document.querySelectorAll('#speeds .btn').forEach(b=>b.classList.toggle('active',+b.dataset.ms===ms));if(playing){clearInterval(timer);timer=setInterval(tick,speedMs);}}
function zoomBy(f){const W=lastW,ci=viewStart+visCount(W)/2;candleW=Math.min(44,Math.max(minW(W),candleW*f));viewStart=ci-visCount(W)/2;clampView(W);render();}
function attach(cv){
 cv.addEventListener('wheel',e=>{e.preventDefault();const W=cv.clientWidth,ai=idxAt(e.offsetX,W),f=e.deltaY<0?1.2:1/1.2;
  candleW=Math.min(44,Math.max(minW(W),candleW*f));viewStart=ai-(e.offsetX-PAD)/candleW;clampView(W);render();},{passive:false});
 cv.addEventListener('mousedown',e=>{drag={x:e.clientX,vs:viewStart};});
 cv.addEventListener('dblclick',()=>{fitAll(cv.clientWidth);render();});}
window.addEventListener('mousemove',e=>{if(!drag)return;viewStart=drag.vs-(e.clientX-drag.x)/candleW;clampView(lastW);render();});
window.addEventListener('mouseup',()=>{drag=null;});
function loadTimeline(fx){stop();$('f1').innerHTML='<span class="muted" style="font-size:12px">computing F1…</span>';
 fetch('/api/timeline?fixture='+encodeURIComponent(fx)).then(r=>r.json()).then(d=>{
 if(d.error){$('hero').textContent=d.error;return;}
 T=d;cascadeIdx=T.cascade_block?nearest(T.cascade_block):-1;firstRedIdx=T.first_red_block?nearest(T.first_red_block):-1;
 playhead=N()-1;$('scrub').max=N()-1;const W=$('cvC').clientWidth||900;fitAll(W);hero();render();});
 fetch('/api/f1?fixture='+encodeURIComponent(fx)).then(r=>r.json()).then(renderF1).catch(()=>{$('f1').innerHTML='<span class="muted">F1 unavailable</span>';});}
$('play').onclick=play;$('scrub').oninput=e=>{stop();playhead=+e.target.value;follow();render();};
$('zin').onclick=()=>zoomBy(1.4);$('zout').onclick=()=>zoomBy(1/1.4);$('fit').onclick=()=>{fitAll(lastW);render();};
['cvC','cvO','cvL'].forEach(id=>attach($(id)));
const sp=$('speeds');SPEEDS.forEach(([ms,lbl])=>{const b=document.createElement('button');b.className='btn'+(ms===80?' active':'');b.textContent=lbl;b.dataset.ms=ms;b.onclick=()=>setSpeed(ms);sp.appendChild(b);});
fetch('/api/fixtures').then(r=>r.json()).then(d=>{const sel=$('fx');
 d.fixtures.forEach(f=>{const o=document.createElement('option');o.value=f.name;o.textContent=`${f.name}  [${f.category}]`;sel.appendChild(o);});
 sel.value=d.default;sel.onchange=()=>loadTimeline(sel.value);loadTimeline(d.default);});
window.addEventListener('resize',()=>{if(T){clampView($('cvC').clientWidth);render();}});
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
