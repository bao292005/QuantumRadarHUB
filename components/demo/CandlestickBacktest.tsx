"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBacktestFixtures, fetchBacktestTimeline, startReplay } from "@/lib/api";
import type { BacktestPoint, BacktestTimeline } from "@/lib/types";

const PAD = 46;
const SPEEDS: [number, string][] = [[160, "0.5x"], [80, "1x"], [40, "2x"], [20, "4x"]];

function scoreColor(level: string | null) {
  return level === "RED" ? "#ff4d4f" : level === "YELLOW" ? "#f5c542" : "#58a6ff";
}

export default function CandlestickBacktest({ autoPlay = false, syncReplay = false, onPoint, initialFixture = "luna_2022_05_09" }: { autoPlay?: boolean; syncReplay?: boolean; onPoint?: (p: BacktestPoint | null) => void; initialFixture?: string } = {}) {
  const [fixtures, setFixtures] = useState<{ name: string; category: string }[]>([]);
  const [fixture, setFixture] = useState(initialFixture);
  const [T, setT] = useState<BacktestTimeline | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(80);
  const [cur, setCur] = useState<{ score: number; level: string | null; block: number; price: number | null; rcs: { contract: string; contribution: number }[] } | null>(null);

  const Tref = useRef<BacktestTimeline | null>(null);
  const cCanvas = useRef<HTMLCanvasElement>(null);
  const oCanvas = useRef<HTMLCanvasElement>(null);
  const view = useRef({ candleW: 6, viewStart: 0 });
  const playhead = useRef(0);
  const cascadeIdx = useRef(-1);
  const firstRedIdx = useRef(-1);
  const drag = useRef<{ x: number; vs: number } | null>(null);
  const timer = useRef<number | null>(null);
  const loopRef = useRef(false);
  const lastW = useRef(900);
  const onPointRef = useRef(onPoint);
  onPointRef.current = onPoint;
  const emittedIdx = useRef(-1);
  const lastEmit = useRef(0);

  const N = () => Tref.current?.points.length ?? 0;
  const nearest = (block: number) => {
    let bi = 0, bd = Infinity;
    Tref.current!.points.forEach((p, i) => { const d = Math.abs(p.block - block); if (d < bd) { bd = d; bi = i; } });
    return bi;
  };
  const visCount = (W: number) => Math.max(1, (W - PAD - 8) / view.current.candleW);
  const minW = (W: number) => (W - PAD - 8) / Math.max(1, N() - 1);
  const clampView = (W: number) => {
    const maxS = Math.max(0, N() - visCount(W));
    view.current.viewStart = Math.min(Math.max(0, view.current.viewStart), maxS);
  };
  const fitAll = (W: number) => { view.current.candleW = minW(W); view.current.viewStart = 0; };
  const xAt = (i: number, W: number) => PAD + (i - view.current.viewStart) * view.current.candleW;
  const range = (W: number): [number, number] => [
    Math.max(0, Math.floor(view.current.viewStart)),
    Math.min(N() - 1, Math.ceil(view.current.viewStart + visCount(W))),
  ];

  const setup = (canvas: HTMLCanvasElement) => {
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth, H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    const c = canvas.getContext("2d")!;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    lastW.current = W;
    return { c, W, H };
  };

  const marks = (c: CanvasRenderingContext2D, W: number, H: number) => {
    const line = (idx: number, col: string, txt: string) => {
      if (idx < 0) return;
      const x = xAt(idx, W); if (x < PAD - 1 || x > W) return;
      c.strokeStyle = col; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(x, 4); c.lineTo(x, H - 4); c.stroke(); c.setLineDash([]);
      c.fillStyle = col; c.font = "10px monospace"; c.fillText(txt, x + 2, 11);
    };
    line(cascadeIdx.current, "#8b949e", "cascade");
    line(firstRedIdx.current, "#ff8c42", "RED");
  };
  const cursor = (c: CanvasRenderingContext2D, W: number, H: number) => {
    const x = xAt(playhead.current, W); if (x < PAD || x > W) return;
    c.strokeStyle = "rgba(230,237,243,.45)"; c.beginPath(); c.moveTo(x, 4); c.lineTo(x, H - 4); c.stroke();
  };

  const drawCandles = () => {
    const cv = cCanvas.current; if (!cv || !Tref.current) return;
    const { c, W, H } = setup(cv); const p = Tref.current.points; c.clearRect(0, 0, W, H);
    const [s, e] = range(W);
    let lo = Infinity, hi = -Infinity;
    for (let i = s; i <= e; i++) { const o = p[i].ohlc; if (!o) continue; lo = Math.min(lo, o.l); hi = Math.max(hi, o.h); }
    if (lo > hi) { lo = 0; hi = 1; } if (hi === lo) hi = lo + 1;
    const y = (v: number) => H - 16 - ((v - lo) / (hi - lo)) * (H - 26);
    for (let i = s; i <= e; i++) {
      if (!p[i].confirmed) continue;   // alert bands = persistence-confirmed alerts (new algo)
      const x = xAt(i, W), w = Math.max(1, view.current.candleW);
      c.fillStyle = p[i].level === "YELLOW" ? "rgba(245,197,66,.14)" : "rgba(255,77,79,.16)";
      c.fillRect(x - w / 2, 4, w, H - 8);
    }
    marks(c, W, H);
    const w = Math.max(1, view.current.candleW * 0.62);
    for (let i = s; i <= e; i++) {
      const o = p[i].ohlc; if (!o) continue; const x = xAt(i, W), up = o.c >= o.o, col = up ? "#26a69a" : "#ef5350";
      c.strokeStyle = col; c.beginPath(); c.moveTo(x, y(o.h)); c.lineTo(x, y(o.l)); c.stroke();
      const yo = y(o.o), yc = y(o.c); c.fillStyle = col; c.fillRect(x - w / 2, Math.min(yo, yc), Math.max(1, w), Math.max(1, Math.abs(yc - yo)));
    }
    cursor(c, W, H);
    c.fillStyle = "#8b949e"; c.font = "10px monospace";
    c.fillText("$" + hi.toFixed(0), 4, y(hi) + 9); c.fillText("$" + lo.toFixed(0), 4, y(lo));
  };

  const drawOsc = () => {
    const cv = oCanvas.current; if (!cv || !Tref.current) return;
    const { c, W, H } = setup(cv); const p = Tref.current.points; c.clearRect(0, 0, W, H);
    const [s, e] = range(W); const y = (v: number) => H - 14 - (v / 100) * (H - 22);
    c.fillStyle = "rgba(255,77,79,.09)"; c.fillRect(PAD, 4, W - PAD - 8, y(90) - 4);
    c.fillStyle = "rgba(245,197,66,.07)"; c.fillRect(PAD, y(90), W - PAD - 8, y(70) - y(90));
    ([[70, "#f5c542"], [90, "#ff4d4f"]] as [number, string][]).forEach(([t, col]) => {
      c.strokeStyle = col; c.globalAlpha = .5; c.beginPath(); c.moveTo(PAD, y(t)); c.lineTo(W - 8, y(t)); c.stroke(); c.globalAlpha = 1;
    });
    marks(c, W, H);
    c.strokeStyle = "#6e7681"; c.setLineDash([5, 4]); c.beginPath();
    let st = false; for (let i = s; i <= e; i++) { const X = xAt(i, W), Y = y(p[i].b0); st ? c.lineTo(X, Y) : c.moveTo(X, Y); st = true; } c.stroke(); c.setLineDash([]);
    c.strokeStyle = "#58a6ff"; c.lineWidth = 1.6; c.beginPath();
    st = false; for (let i = s; i <= e; i++) { const X = xAt(i, W), Y = y(p[i].score); st ? c.lineTo(X, Y) : c.moveTo(X, Y); st = true; } c.stroke();
    cursor(c, W, H);
    const pc = p[playhead.current], cx = xAt(playhead.current, W);
    if (cx >= PAD && cx <= W) { c.fillStyle = scoreColor(pc.level); c.beginPath(); c.arc(cx, y(pc.score), 3.2, 0, 7); c.fill(); }
    c.fillStyle = "#8b949e"; c.font = "10px monospace"; c.fillText("90", 6, y(90) + 3); c.fillText("70", 6, y(70) + 3);
  };

  const draw = useCallback(() => {
    drawCandles(); drawOsc();
    const p = Tref.current?.points[playhead.current];
    if (p) setCur({ score: p.score, level: p.level, block: p.block, price: p.price, rcs: p.rcs });
    if (onPointRef.current && playhead.current !== emittedIdx.current) {
      const now = typeof performance !== "undefined" ? performance.now() : Date.now();
      if (now - lastEmit.current > 400) {
        lastEmit.current = now;
        emittedIdx.current = playhead.current;
        onPointRef.current(p ?? null);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // load fixtures once
  useEffect(() => { fetchBacktestFixtures().then((d) => setFixtures(d.fixtures)).catch(() => {}); }, []);

  // load timeline on fixture change
  useEffect(() => {
    const controller = new AbortController();
    fetchBacktestTimeline(fixture, controller.signal).then((d) => {
      if (d.error) return;
      Tref.current = d; setT(d);
      playhead.current = d.points.length - 1;
      cascadeIdx.current = d.cascade_block ? nearest(d.cascade_block) : -1;
      firstRedIdx.current = d.first_red_block ? nearest(d.first_red_block) : -1;
      const W = cCanvas.current?.clientWidth || 900; fitAll(W); draw();
    }).catch(() => {});
    return () => controller.abort();
  }, [fixture, draw]);

  const stop = useCallback(() => setPlaying(false), []);
  const follow = () => {
    const W = lastW.current, x = xAt(playhead.current, W);
    if (x < PAD + view.current.candleW || x > W - 24) { view.current.viewStart = playhead.current - visCount(W) * 0.5; clampView(W); }
  };
  const tick = useCallback(() => {
    if (playhead.current >= N() - 1) {
      if (loopRef.current) playhead.current = 0; else { setPlaying(false); return; }
    } else playhead.current += 1;
    follow(); draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draw]);
  const play = () => {
    if (playing) { setPlaying(false); return; }
    loopRef.current = false;
    if (playhead.current >= N() - 1) playhead.current = 0;
    setPlaying(true);
  };
  // single interval owner: (re)starts whenever playing/speed change
  useEffect(() => {
    if (!playing) { if (timer.current) { window.clearInterval(timer.current); timer.current = null; } return; }
    if (timer.current) window.clearInterval(timer.current);
    timer.current = window.setInterval(tick, speed);
    return () => { if (timer.current) { window.clearInterval(timer.current); timer.current = null; } };
  }, [playing, speed, tick]);

  // auto-play a looping crisis when embedded on the main page (chart reacts to the algorithm)
  useEffect(() => {
    if (!autoPlay || !T) return;
    loopRef.current = true; playhead.current = 0; setPlaying(true);
  }, [T, autoPlay]);

  // sync the backend replay to the same crisis so the extension goes live too
  useEffect(() => {
    if (!syncReplay || !T) return;
    const replaySpeed = Math.max(0.5, Math.round((300 / speed) * 10) / 10);
    startReplay(T.fixture, replaySpeed).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [T, syncReplay]);

  const zoomBy = (f: number) => {
    const W = lastW.current, ci = view.current.viewStart + visCount(W) / 2;
    view.current.candleW = Math.min(44, Math.max(minW(W), view.current.candleW * f));
    view.current.viewStart = ci - visCount(W) / 2; clampView(W); draw();
  };

  const onWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const W = (e.currentTarget as HTMLCanvasElement).clientWidth;
    const ai = view.current.viewStart + (e.nativeEvent.offsetX - PAD) / view.current.candleW;
    const f = e.deltaY < 0 ? 1.2 : 1 / 1.2;
    view.current.candleW = Math.min(44, Math.max(minW(W), view.current.candleW * f));
    view.current.viewStart = ai - (e.nativeEvent.offsetX - PAD) / view.current.candleW; clampView(W); draw();
  };
  useEffect(() => {
    const onMove = (e: MouseEvent) => { if (!drag.current) return; view.current.viewStart = drag.current.vs - (e.clientX - drag.current.x) / view.current.candleW; clampView(lastW.current); draw(); };
    const onUp = () => { drag.current = null; };
    window.addEventListener("mousemove", onMove); window.addEventListener("mouseup", onUp);
    const onResize = () => { clampView(cCanvas.current?.clientWidth || 900); draw(); };
    window.addEventListener("resize", onResize);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); window.removeEventListener("resize", onResize); };
  }, [draw]);

  const heroText = T
    ? T.lead_hours != null
      ? `🔴 RED fired ${T.lead_hours}h BEFORE cascade — ${T.event_name} [${T.category}]`
      : T.category === "fp_control"
        ? `🟢 ${T.event_name} — control, no pre-cascade alert expected [${T.category}]`
        : `${T.event_name} [${T.category}]`
    : "loading…";
  const heroColor = T?.lead_hours != null ? "#ff4d4f" : T?.category === "fp_control" ? "#3fb950" : "#1f2937";

  const canvasStyle: React.CSSProperties = { width: "100%", display: "block", cursor: "crosshair" };
  const cardStyle: React.CSSProperties = { background: "#0e1420", border: "1px solid #1f2937", borderRadius: 10, padding: 10 };
  const btn: React.CSSProperties = { background: "#1f2937", border: "1px solid #374151", color: "#e6edf3", borderRadius: 6, padding: "6px 10px", fontFamily: "inherit", cursor: "pointer", fontSize: 12 };

  return (
    <div style={{ flex: 1, minWidth: 0, background: "#0b0f1a", color: "#e6edf3", fontFamily: "ui-monospace, Menlo, monospace", padding: 16, overflow: "auto" }}>
      <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>QuantumRadar — Backtest nến (dữ liệu thật)</div>
      <div style={{ ...cardStyle, marginBottom: 10, fontSize: 14, borderColor: heroColor }}>{heroText}</div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: "#8b949e" }}>crisis</span>
        <select value={fixture} onChange={(e) => setFixture(e.target.value)} style={btn}>
          {fixtures.map((f) => <option key={f.name} value={f.name}>{f.name} [{f.category}]</option>)}
        </select>
        <button style={btn} onClick={play}>{playing ? "⏸ pause" : "▶ play"}</button>
        <span style={{ fontSize: 12, color: "#8b949e" }}>speed</span>
        {SPEEDS.map(([ms, lbl]) => (
          <button key={ms} style={{ ...btn, background: speed === ms ? "#1f6feb" : "#1f2937", borderColor: speed === ms ? "#1f6feb" : "#374151" }} onClick={() => setSpeed(ms)}>{lbl}</button>
        ))}
        <span style={{ width: 8 }} />
        <button style={btn} onClick={() => zoomBy(1.4)}>＋</button>
        <button style={btn} onClick={() => zoomBy(1 / 1.4)}>－</button>
        <button style={btn} onClick={() => { fitAll(lastW.current); draw(); }}>⤢ fit</button>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#8b949e" }}>wheel=zoom · drag=pan</span>
      </div>
      <input type="range" min={0} max={Math.max(0, (T?.points.length ?? 1) - 1)} value={cur ? Math.min(playhead.current, (T?.points.length ?? 1) - 1) : 0}
        onChange={(e) => { stop(); playhead.current = Number(e.target.value); follow(); draw(); }}
        style={{ width: "100%", marginBottom: 10 }} />
      <div style={{ display: "flex", gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...cardStyle, marginBottom: 8 }}>
            <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 2 }}>ETH / USDC — candlesticks (alert bands shaded)</div>
            <canvas ref={cCanvas} style={{ ...canvasStyle, height: 300 }}
              onWheel={onWheel} onMouseDown={(e) => { drag.current = { x: e.clientX, vs: view.current.viewStart }; }} onDoubleClick={() => { fitAll(cCanvas.current!.clientWidth); draw(); }} />
          </div>
          <div style={cardStyle}>
            <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 2 }}>FRAGILITY oscillator — RED≥90 / YELLOW≥70 (+ B0 baseline)</div>
            <canvas ref={oCanvas} style={{ ...canvasStyle, height: 150 }}
              onWheel={onWheel} onMouseDown={(e) => { drag.current = { x: e.clientX, vs: view.current.viewStart }; }} onDoubleClick={() => { fitAll(oCanvas.current!.clientWidth); draw(); }} />
          </div>
        </div>
        <div style={{ ...cardStyle, width: 220 }}>
          <div style={{ fontSize: 13, letterSpacing: 2, color: scoreColor(cur?.level ?? null) }}>{cur?.level ?? "CALM"}</div>
          <div style={{ fontSize: 44, fontWeight: 700, color: cur?.level === "RED" ? "#ff4d4f" : cur?.level === "YELLOW" ? "#f5c542" : "#e6edf3" }}>{cur?.score.toFixed(1) ?? "0"}</div>
          <div style={{ fontSize: 12, color: "#8b949e", margin: "6px 0 12px" }}>block {cur?.block ?? "—"}{cur?.price ? ` · ETH $${cur.price}` : ""}</div>
          <div style={{ fontSize: 12, color: "#8b949e" }}>RCS — epicenter</div>
          {(cur?.rcs ?? []).map((r) => (
            <div key={r.contract} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid #1f2937", fontSize: 12 }}>
              <span>{r.contract}</span><span>{r.contribution}</span>
            </div>
          ))}
          {(!cur?.rcs || cur.rcs.length === 0) && <div style={{ color: "#8b949e" }}>—</div>}
        </div>
      </div>
    </div>
  );
}
