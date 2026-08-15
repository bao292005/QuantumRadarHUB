'use client'

import { useEffect, useRef, useState } from 'react'

// ── Seeded RNG ──
function mulberry32(seed: number) {
  return function () {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed)
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t
    return ((t ^ t >>> 14) >>> 0) / 4294967296
  }
}

function makeCandles(count: number, seed: number, startPrice: number, driftFn: (i: number) => number) {
  const rand = mulberry32(seed)
  const out: { open: number; close: number; high: number; low: number; volume: number }[] = []
  let price = startPrice
  for (let i = 0; i < count; i++) {
    const open = price
    const change = (rand() - 0.5 + driftFn(i)) * (startPrice * 0.01)
    const close = Math.max(startPrice * 0.7, open + change)
    const high = Math.max(open, close) + rand() * (startPrice * 0.003)
    const low  = Math.min(open, close) - rand() * (startPrice * 0.003)
    const volume = 100 + rand() * 400
    out.push({ open, close, high, low, volume })
    price = close
  }
  return out
}

// ETHUSDT – slight downtrend in tail
const ETH_CANDLES = makeCandles(80, 0xdeadbeef, 3420, (i) => (i > 42 ? -0.55 : 0.1))
// AAVEUSDT – aggressive drop in last third (liquidity drain scenario)
const AAVE_CANDLES = makeCandles(80, 0xcafebabe, 187.4, (i) => {
  if (i < 50) return 0.08
  if (i < 65) return -0.9   // sharp sell-off
  return -0.4               // continued weakness
})

const ETH_SR  = [{ price: 3580, label: 'R1', color: '#ef4444' }, { price: 3490, label: 'S1', color: '#22c55e' }, { price: 3350, label: 'S2', color: '#22c55e' }]
const AAVE_SR = [{ price: 195,  label: 'R1', color: '#ef4444' }, { price: 178,  label: 'S1', color: '#22c55e' }, { price: 162,  label: 'S2', color: '#22c55e' }]

const ETH_MARKERS  = [
  { idx: 52, label: '🚨 Liquidity Risk',    color: '#ef4444', glow: 'rgba(239,68,68,0.3)' },
  { idx: 63, label: '🐋 Whale Activity',    color: '#f59e0b', glow: 'rgba(245,158,11,0.25)' },
  { idx: 71, label: '⚡ Stablecoin Stress', color: '#00C2FF', glow: 'rgba(0,194,255,0.25)' },
]
const AAVE_MARKERS = [
  { idx: 50, label: '🐋 Whale Withdraw',     color: '#f59e0b', glow: 'rgba(245,158,11,0.28)' },
  { idx: 60, label: '📉 TVL Decline',        color: '#ef4444', glow: 'rgba(239,68,68,0.32)' },
  { idx: 72, label: '🚨 Risk Escalation',    color: '#ef4444', glow: 'rgba(239,68,68,0.4)' },
]

// ── Canvas draw ──
function drawChart(
  canvas: HTMLCanvasElement,
  candles: ReturnType<typeof makeCandles>,
  srLines: typeof ETH_SR,
  zoneStart: number,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const dpr = window.devicePixelRatio || 1
  const w = canvas.offsetWidth
  const h = canvas.offsetHeight
  if (!w || !h) return
  canvas.width  = w * dpr
  canvas.height = h * dpr
  ctx.scale(dpr, dpr)

  const PAD_L = 6, PAD_R = 68, PAD_T = 12
  const VOL_H = Math.round(h * 0.18)
  const PAD_B = VOL_H + 2
  const CW     = (w - PAD_L - PAD_R) / candles.length
  const CHART_H = h - PAD_T - PAD_B
  const prices  = candles.flatMap((c) => [c.high, c.low])
  const MIN_P   = Math.min(...prices) - prices[0] * 0.01
  const MAX_P   = Math.max(...prices) + prices[0] * 0.015
  const RANGE   = MAX_P - MIN_P
  const toY = (p: number) => PAD_T + ((MAX_P - p) / RANGE) * CHART_H
  const toX = (i: number) => PAD_L + i * CW + CW / 2

  // Background
  ctx.fillStyle = '#131722'; ctx.fillRect(0, 0, w, h)
  // Price axis bg
  ctx.fillStyle = '#151c2c'; ctx.fillRect(w - PAD_R, 0, PAD_R, h)
  ctx.strokeStyle = '#252d3d'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(w - PAD_R, 0); ctx.lineTo(w - PAD_R, h); ctx.stroke()

  // Grid + price labels
  for (let i = 0; i <= 7; i++) {
    const y = PAD_T + (i / 7) * CHART_H
    const p = MAX_P - (i / 7) * RANGE
    ctx.strokeStyle = '#1a2234'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(w - PAD_R, y); ctx.stroke()
    ctx.fillStyle = '#4a5568'; ctx.font = '10px Inter, sans-serif'; ctx.textAlign = 'left'
    ctx.fillText(p.toFixed(p > 100 ? 1 : 3), w - PAD_R + 4, y + 3)
  }

  // S/R lines
  srLines.forEach(({ price, label, color }) => {
    const y = toY(price)
    if (y < PAD_T || y > PAD_T + CHART_H) return
    ctx.strokeStyle = color + '70'; ctx.lineWidth = 1; ctx.setLineDash([5, 4])
    ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(w - PAD_R, y); ctx.stroke()
    ctx.setLineDash([])
    const lw = 30, lh = 14
    ctx.fillStyle = color + '22'; ctx.strokeStyle = color + '80'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.roundRect(w - PAD_R + 2, y - lh / 2, lw, lh, 3); ctx.fill(); ctx.stroke()
    ctx.fillStyle = color; ctx.font = 'bold 9px Inter, sans-serif'; ctx.textAlign = 'center'
    ctx.fillText(label, w - PAD_R + 2 + lw / 2, y + 3)
  })

  // EMA
  let ema = candles[0].close; const alpha = 2 / 21
  const emaVals = candles.map((c) => { ema = c.close * alpha + ema * (1 - alpha); return ema })
  ctx.strokeStyle = '#818cf8'; ctx.lineWidth = 1.2; ctx.globalAlpha = 0.8
  ctx.beginPath()
  emaVals.forEach((p, i) => { const x = toX(i); const y = toY(p); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y) })
  ctx.stroke(); ctx.globalAlpha = 1

  // MA20
  const ma20: number[] = []
  for (let i = 0; i < candles.length; i++) {
    ma20.push(i < 19 ? candles[i].close : candles.slice(i - 19, i + 1).reduce((s, c) => s + c.close, 0) / 20)
  }
  ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1.2; ctx.globalAlpha = 0.8; ctx.setLineDash([3, 2])
  ctx.beginPath()
  ma20.forEach((p, i) => { const x = toX(i); const y = toY(p); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y) })
  ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1

  // Candles
  candles.forEach((c, i) => {
    const x = toX(i); const isUp = c.close >= c.open
    const color = isUp ? '#26a69a' : '#ef5350'
    ctx.strokeStyle = color; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(x, toY(c.high)); ctx.lineTo(x, toY(c.low)); ctx.stroke()
    const bTop = toY(Math.max(c.open, c.close)); const bBot = toY(Math.min(c.open, c.close))
    ctx.fillStyle = color; ctx.fillRect(x - CW * 0.38, bTop, CW * 0.76, Math.max(bBot - bTop, 1))
  })

  // Anomaly zone
  const x0 = PAD_L + zoneStart * CW, x1 = PAD_L + candles.length * CW
  const grad = ctx.createLinearGradient(x0, 0, x1, 0)
  grad.addColorStop(0, 'rgba(0,194,255,0)'); grad.addColorStop(0.25, 'rgba(0,194,255,0.05)'); grad.addColorStop(1, 'rgba(239,68,68,0.12)')
  ctx.fillStyle = grad; ctx.fillRect(x0, PAD_T, x1 - x0, CHART_H)
  ctx.strokeStyle = 'rgba(0,194,255,0.5)'; ctx.lineWidth = 1; ctx.setLineDash([4, 3])
  ctx.beginPath(); ctx.moveTo(x0, PAD_T); ctx.lineTo(x0, PAD_T + CHART_H); ctx.stroke(); ctx.setLineDash([])

  // Current price line
  const last = candles[candles.length - 1].close; const py = toY(last)
  ctx.strokeStyle = '#00C2FF'; ctx.lineWidth = 1; ctx.setLineDash([4, 3])
  ctx.beginPath(); ctx.moveTo(PAD_L, py); ctx.lineTo(w - PAD_R, py); ctx.stroke(); ctx.setLineDash([])
  const bw = 62, bh = 16
  ctx.fillStyle = '#00C2FF'; ctx.beginPath(); ctx.roundRect(w - PAD_R + 2, py - bh / 2, bw - 4, bh, 3); ctx.fill()
  ctx.fillStyle = '#000'; ctx.font = 'bold 10px JetBrains Mono, monospace'; ctx.textAlign = 'center'
  ctx.fillText(last.toFixed(last > 100 ? 2 : 4), w - PAD_R + 2 + (bw - 4) / 2, py + 4)

  // Volume sub-chart
  const volTop = h - VOL_H
  ctx.fillStyle = '#0e1621'; ctx.fillRect(0, volTop, w - PAD_R, VOL_H)
  ctx.strokeStyle = '#252d3d'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(0, volTop); ctx.lineTo(w - PAD_R, volTop); ctx.stroke()
  const maxV = Math.max(...candles.map((c) => c.volume))
  candles.forEach((c, i) => {
    const x = PAD_L + i * CW; const isUp = c.close >= c.open
    const vh = ((c.volume / maxV) * (VOL_H - 6)) | 0
    ctx.fillStyle = isUp ? 'rgba(38,166,154,0.5)' : 'rgba(239,83,80,0.5)'
    ctx.fillRect(x + 0.5, volTop + (VOL_H - 6 - vh), CW - 1, vh)
  })
  ctx.fillStyle = '#4a5568'; ctx.font = '9px Inter, sans-serif'; ctx.textAlign = 'left'
  ctx.fillText('Volume', PAD_L + 4, volTop + 10)
}

// ── Toolbar icons ──
const TOOLBAR = [
  <svg key="a" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="3.5"/><line x1="10" y1="1" x2="10" y2="5.5"/><line x1="10" y1="14.5" x2="10" y2="19"/><line x1="1" y1="10" x2="5.5" y2="10"/><line x1="14.5" y1="10" x2="19" y2="10"/></svg>,
  <svg key="b" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="3" y1="16" x2="17" y2="4"/><circle cx="3" cy="16" r="1.5" fill="currentColor"/><circle cx="17" cy="4" r="1.5" fill="currentColor"/></svg>,
  <svg key="c" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="3" y1="10" x2="17" y2="10"/><circle cx="3" cy="10" r="1.5" fill="currentColor"/></svg>,
  <svg key="d" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.3"><line x1="3" y1="4" x2="17" y2="4"/><line x1="3" y1="9" x2="17" y2="9"/><line x1="3" y1="13" x2="17" y2="13"/><line x1="3" y1="17" x2="17" y2="17"/><line x1="3" y1="4" x2="3" y2="17"/></svg>,
  <svg key="e" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="5" width="14" height="10" rx="1"/></svg>,
  <svg key="f" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M4 5h12M10 5v10M7 15h6"/></svg>,
  <svg key="g" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="4" y1="16" x2="15" y2="5"/><polyline points="8,5 15,5 15,12"/></svg>,
  <svg key="h" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M15 3l2 2-9.5 9.5-2-2L15 3z"/><path d="M5.5 14.5c-.5 1.5-2 2-2 2s.5-1.5 2-2z"/></svg>,
  <svg key="i" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="9" cy="9" r="5.5"/><line x1="13.5" y1="13.5" x2="17" y2="17"/></svg>,
  <svg key="j" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.4"><line x1="3" y1="10" x2="17" y2="10"/><line x1="3" y1="7" x2="3" y2="13"/><line x1="17" y1="7" x2="17" y2="13"/></svg>,
]

const WATCHLIST_PAGE1 = [
  { sym: 'ETHUSDT',  price: '3,421.85', chg: '-1.24%', up: false, active: true  },
  { sym: 'BTCUSDT',  price: '67,342.10',chg: '+0.83%', up: true,  active: false },
  { sym: 'AAVEUSDT', price: '184.72',   chg: '-3.41%', up: false, active: false },
  { sym: 'CRVUSDT',  price: '0.4821',   chg: '-6.18%', up: false, active: false },
  { sym: 'SOLUSDT',  price: '183.54',   chg: '+1.92%', up: true,  active: false },
  { sym: 'LINKUSDT', price: '14.83',    chg: '-0.67%', up: false, active: false },
  { sym: 'UNIUSDT',  price: '7.234',    chg: '+2.11%', up: true,  active: false },
  { sym: 'BNBUSDT',  price: '602.40',   chg: '+0.44%', up: true,  active: false },
  { sym: 'MKRUSDT',  price: '1,842.00', chg: '-2.87%', up: false, active: false },
  { sym: 'COMPUSDT', price: '54.61',    chg: '-1.99%', up: false, active: false },
]

const WATCHLIST_PAGE2 = WATCHLIST_PAGE1.map((w) => ({
  ...w,
  active: w.sym === 'AAVEUSDT',
}))

const TFS = ['1m','3m','5m','15m','30m','1H','2H','4H','1D','1W','1M']
const SCAN_MSGS = [
  'Scanning Market…',
  'Analyzing On-chain Activity…',
  'Detecting Systemic Risks…',
  'Monitoring Liquidity Flows…',
  'Cross-referencing Whale Wallets…',
]
const X_LABELS = [0, 11, 22, 33, 44, 55, 66, 77].map((idx, i) => ({
  idx, label: ['00:00','11:00','22:00','09:00','20:00','07:00','18:00','05:00'][i],
}))

type LegacyPage = 1 | 2 | 3 | 4 | 5 | 6

export default function TradingViewMock() {
  const [page] = useState<LegacyPage>(1)
  const onNavigate = (_page: LegacyPage) => {}
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const [scanIdx, setScanIdx] = useState(0)
  const [alertDismissed, setAlertDismissed] = useState(false)
  const [hoveredMarker, setHoveredMarker] = useState<number | null>(null)

  const isAave    = page !== 1
  const candles   = isAave ? AAVE_CANDLES  : ETH_CANDLES
  const srLines   = isAave ? AAVE_SR       : ETH_SR
  const markers   = isAave ? AAVE_MARKERS  : ETH_MARKERS
  const watchlist = isAave ? WATCHLIST_PAGE2 : WATCHLIST_PAGE1
  const symbol    = isAave ? 'AAVEUSDT'    : 'ETHUSDT'
  const lastPrice = candles[candles.length - 1].close
  const zoneStart = isAave ? 48 : 58

  useEffect(() => { setAlertDismissed(false) }, [page])

  useEffect(() => {
    const id = setInterval(() => setScanIdx((s) => (s + 1) % SCAN_MSGS.length), 2400)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return
    const draw = () => drawChart(canvas, candles, srLines, zoneStart)
    draw()
    const ro = new ResizeObserver(draw); ro.observe(canvas)
    return () => ro.disconnect()
  }, [candles, srLines, zoneStart])

  const priceColor = '#ef5350'
  const priceSign  = isAave ? '▼ −3.41%' : '▼ −1.24%'

  return (
    <div style={{ flex: 1, position: 'relative', background: '#131722', overflow: 'hidden', display: 'flex', flexDirection: 'column', minWidth: 0 }}>

      {/* ── TOP BAR ── */}
      <div style={{ height: 38, background: '#1e2433', borderBottom: '1px solid #252d3d', display: 'flex', alignItems: 'center', padding: '0 10px', gap: 0, flexShrink: 0, zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingRight: 14, borderRight: '1px solid #252d3d', marginRight: 12 }}>
          <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="6" fill="#2962FF"/>
            <path d="M8 22l8-12 8 12" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span style={{ color: '#d1d5db', fontSize: 13, fontFamily: 'Outfit, sans-serif', fontWeight: 600 }}>TradingView</span>
        </div>
        {['Chart','Screener','Ideas','News','Pine Editor','Alerts'].map((tab) => (
          <span key={tab} style={{ color: tab === 'Chart' ? '#e2e8f0' : '#6b7280', fontSize: 12, padding: '0 10px', height: 38, display: 'flex', alignItems: 'center', borderBottom: tab === 'Chart' ? '2px solid #2962FF' : '2px solid transparent', cursor: 'default', fontFamily: 'Inter, sans-serif' }}>{tab}</span>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingRight: 10 }}>
          <span style={{ color: '#6b7280', fontSize: 11, fontFamily: 'Inter, sans-serif' }}>BINANCE:</span>
          <span style={{ color: '#e2e8f0', fontSize: 12, fontFamily: 'Outfit, sans-serif', fontWeight: 700 }}>{symbol}</span>
          <span style={{ color: priceColor, fontSize: 12, fontFamily: 'JetBrains Mono, monospace' }}>{lastPrice.toFixed(page === 1 ? 2 : 3)}</span>
          <span style={{ color: priceColor, fontSize: 11 }}>{priceSign}</span>
          <div style={{ width: 1, height: 18, background: '#252d3d' }} />
          {page === 1 ? <>
            <span style={{ color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>O: 3,482.10</span>
            <span style={{ color: '#26a69a', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>H: 3,561.40</span>
            <span style={{ color: '#ef5350', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>L: 3,318.70</span>
          </> : <>
            <span style={{ color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>O: 192.40</span>
            <span style={{ color: '#26a69a', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>H: 196.80</span>
            <span style={{ color: '#ef5350', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>L: 171.20</span>
          </>}
          <span style={{ color: '#6b7280', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>C: {lastPrice.toFixed(page === 1 ? 2 : 3)}</span>
        </div>
        {['⚙','📷','⊞'].map((ic, i) => (
          <div key={i} style={{ width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', fontSize: 14, cursor: 'default', borderRadius: 4 }}>{ic}</div>
        ))}
      </div>

      {/* ── BODY ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>

        {/* Left toolbar */}
        <div style={{ width: 44, background: '#1a2236', borderRight: '1px solid #252d3d', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '8px 0', gap: 2, flexShrink: 0, zIndex: 10 }}>
          {TOOLBAR.map((svg, i) => (
            <div key={i} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 5, color: i === 0 ? '#00C2FF' : '#6b7280', background: i === 0 ? 'rgba(0,194,255,0.1)' : 'transparent', cursor: 'default' }}>
              {svg}
            </div>
          ))}
          <div style={{ flex: 1 }} />
          <div style={{ width: 28, height: 1, background: '#252d3d', margin: '4px 0' }} />
          <div style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', cursor: 'default' }}>
            <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="10" cy="10" r="7.5"/><line x1="10" y1="6" x2="10" y2="10.5"/><circle cx="10" cy="13" r="0.8" fill="currentColor"/></svg>
          </div>
        </div>

        {/* Chart area */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minWidth: 0 }}>

          {/* Legend */}
          <div style={{ position: 'absolute', top: 8, left: 10, zIndex: 5, pointerEvents: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
              <span style={{ color: '#9ca3af', fontSize: 12, fontFamily: 'Inter, sans-serif' }}>BINANCE</span>
              <span style={{ color: '#e2e8f0', fontSize: 15, fontFamily: 'Outfit, sans-serif', fontWeight: 700 }}>{symbol}</span>
              <span style={{ background: '#252d3d', color: '#9ca3af', fontSize: 10, padding: '1px 6px', borderRadius: 3, fontFamily: 'Inter, sans-serif' }}>1H</span>
              {page === 2 && <span style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444', fontSize: 10, padding: '1px 6px', borderRadius: 3, fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>⚠ AI Alert Active</span>}
            </div>
            <div style={{ display: 'flex', gap: 14 }}>
              <span style={{ color: '#f59e0b', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}>MA(20) {page === 1 ? '3481.4' : '186.42'}</span>
              <span style={{ color: '#818cf8', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}>EMA(20) {page === 1 ? '3476.2' : '184.91'}</span>
              <span style={{ color: '#26a69a', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}>VOL {page === 1 ? '2.84M' : '1.12M'}</span>
            </div>
          </div>

          <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />

          {/* X-axis labels */}
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 18, pointerEvents: 'none', zIndex: 4 }}>
            {X_LABELS.map(({ idx, label }) => (
              <span key={idx} style={{ position: 'absolute', left: `${(idx / (candles.length - 1)) * 100}%`, transform: 'translateX(-50%)', color: '#4a5568', fontSize: 10, fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>{label}</span>
            ))}
          </div>

          {/* AI Risk Markers */}
          {markers.map((m, mi) => (
            <div
              key={mi}
              onMouseEnter={() => setHoveredMarker(mi)}
              onMouseLeave={() => setHoveredMarker(null)}
              style={{ position: 'absolute', left: `calc(${(m.idx / candles.length) * 100}% + 4px)`, top: '10%', zIndex: 6, cursor: 'default', transform: 'translateX(-50%)' }}
            >
              <div style={{ position: 'absolute', left: '50%', top: 26, width: 1, height: 70, background: `linear-gradient(to bottom, ${m.color}80, transparent)`, transform: 'translateX(-50%)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, background: '#0d1829', border: `1px solid ${m.color}60`, borderRadius: 6, padding: '3px 8px', boxShadow: `0 0 12px ${m.glow}`, whiteSpace: 'nowrap' }}>
                <span style={{ fontSize: 10 }}>{m.label.split(' ')[0]}</span>
                <span style={{ color: m.color, fontSize: 10, fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>{m.label.split(' ').slice(1).join(' ')}</span>
              </div>
              {hoveredMarker === mi && (
                <div style={{ position: 'absolute', top: 36, left: '50%', transform: 'translateX(-50%)', background: '#0d1829', border: `1px solid ${m.color}40`, borderRadius: 8, padding: '8px 12px', boxShadow: '0 4px 24px rgba(0,0,0,0.6)', width: 210, zIndex: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: m.color, boxShadow: `0 0 6px ${m.color}` }} />
                    <span style={{ color: '#00C2FF', fontSize: 10, fontFamily: 'Outfit, sans-serif', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>QuantumRadar Alert</span>
                  </div>
                  <p style={{ color: '#cbd5e1', fontSize: 11, fontFamily: 'Inter, sans-serif', margin: 0, lineHeight: 1.5 }}>
                    QuantumRadar detected abnormal on-chain activity. Risk escalation confirmed with 89% confidence.
                  </p>
                </div>
              )}
            </div>
          ))}

          {/* Alert popup */}
          {!alertDismissed && (
            <div style={{ position: 'absolute', top: 12, right: 78, zIndex: 15, background: 'linear-gradient(135deg, #0d1829 0%, #111827 100%)', border: `1px solid rgba(239,68,68,${page === 2 ? 0.7 : 0.4})`, borderRadius: 12, padding: '12px 14px', width: 220, boxShadow: `0 8px 32px rgba(0,0,0,0.5), 0 0 ${page === 2 ? 30 : 20}px rgba(239,68,68,${page === 2 ? 0.2 : 0.1})`, animation: 'fade-up 0.5s cubic-bezier(0.16,1,0.3,1) forwards' }}>
              <button onClick={() => setAlertDismissed(true)} style={{ position: 'absolute', top: 8, right: 10, background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: 0 }}>×</button>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 7 }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 8px #ef4444', animation: 'blink-dot 1s ease-in-out infinite' }} />
                <span style={{ color: '#ef4444', fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 12, letterSpacing: '0.04em' }}>🚨 QUANTUM ALERT</span>
              </div>
              {page === 1 ? <>
                <div style={{ color: '#f1f5f9', fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Liquidity Shock Risk</div>
                {/* 72% hero badge */}
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                  <span style={{ background: 'rgba(249,115,22,0.18)', border: '1px solid rgba(249,115,22,0.5)', borderRadius: 7, padding: '3px 12px', color: '#f97316', fontFamily: 'JetBrains Mono, monospace', fontWeight: 900, fontSize: 22, boxShadow: '0 0 14px rgba(249,115,22,0.25)' }}>72%</span>
                  <span style={{ color: '#d1d5db', fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 500 }}>khả năng xảy ra</span>
                </div>
                <div style={{ color: '#6b7280', fontSize: 10, fontFamily: 'Inter, sans-serif', marginBottom: 9 }}>trong 12–24 giờ tới</div>
                {/* Impact card */}
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.28)', borderRadius: 7, padding: '5px 10px', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12 }}>📉</span>
                  <span style={{ color: '#fca5a5', fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>Tác động danh mục dự kiến:</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, fontSize: 13, color: '#ef4444', marginLeft: 'auto' }}>-8%</span>
                </div>
              </> : <>
                <div style={{ color: '#f1f5f9', fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Liquidity Shock Risk</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                  <span style={{ background: 'rgba(239,68,68,0.18)', border: '1px solid rgba(239,68,68,0.5)', borderRadius: 7, padding: '3px 12px', color: '#ef4444', fontFamily: 'JetBrains Mono, monospace', fontWeight: 900, fontSize: 22, boxShadow: '0 0 14px rgba(239,68,68,0.25)' }}>91%</span>
                  <span style={{ color: '#d1d5db', fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 500 }}>khả năng xảy ra</span>
                </div>
                <div style={{ color: '#6b7280', fontSize: 10, fontFamily: 'Inter, sans-serif', marginBottom: 9 }}>trong 12–24 giờ tới · tăng từ 72%</div>
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.28)', borderRadius: 7, padding: '5px 10px', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12 }}>📉</span>
                  <span style={{ color: '#fca5a5', fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>Tác động danh mục dự kiến:</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, fontSize: 13, color: '#ef4444', marginLeft: 'auto' }}>-8%</span>
                </div>
              </>}
              <button
                onClick={() => { setAlertDismissed(true); if (page === 1) onNavigate(2) }}
                style={{ width: '100%', padding: '7px 0', background: page === 2 ? 'rgba(239,68,68,0.15)' : 'rgba(0,194,255,0.1)', border: `1px solid ${page === 2 ? 'rgba(239,68,68,0.4)' : 'rgba(0,194,255,0.35)'}`, borderRadius: 7, color: page === 2 ? '#ef4444' : '#00C2FF', fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, transition: 'all 0.2s' }}
              >
                {page === 2 ? '⚠ Đã Xác Nhận' : 'Xem Chi Tiết →'}
              </button>
            </div>
          )}

          {/* Scanning status */}
          <div style={{ position: 'absolute', bottom: 20, left: 12, zIndex: 8, display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(11,18,32,0.85)', backdropFilter: 'blur(6px)', border: '1px solid rgba(0,194,255,0.2)', borderRadius: 8, padding: '5px 12px' }}>
            <div style={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
              <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: page === 6 ? '#22c55e' : isAave ? '#ef4444' : '#00C2FF', boxShadow: `0 0 6px ${page === 6 ? '#22c55e' : isAave ? '#ef4444' : '#00C2FF'}` }} />
              <div style={{ position: 'absolute', inset: -3, borderRadius: '50%', border: `1.5px solid ${page === 6 ? '#22c55e' : isAave ? '#ef4444' : '#00C2FF'}`, animation: 'pulse-ring 2s ease-in-out infinite', opacity: 0 }} />
            </div>
            <span style={{ color: page === 4 ? '#c4b5fd' : isAave ? '#fca5a5' : '#00C2FF', fontSize: 11, fontFamily: 'JetBrains Mono, monospace', fontWeight: 500 }}>
              {page === 2 ? 'QuantumRadar AI · ⚠ Early Warning Active'
               : page === 3 ? 'QuantumRadar AI · 🔮 Forecasting Future Scenarios...'
               : page === 4 ? 'QuantumRadar AI · 💼 Portfolio Analysis Running...'
               : page === 5 ? 'QuantumRadar AI · 🤖 AI đang xây dựng phương án phòng thủ...'
               : page === 6 ? 'QuantumRadar AI · 🟢 Auto Protection Ready'
               : `QuantumRadar AI · ${SCAN_MSGS[scanIdx]}`}
            </span>
          </div>

          {/* Anomaly label */}
          <div style={{ position: 'absolute', bottom: 22, right: 82, zIndex: 7, background: 'rgba(0,194,255,0.08)', border: '1px solid rgba(0,194,255,0.3)', borderRadius: 6, padding: '3px 10px', pointerEvents: 'none' }}>
            <span style={{ color: '#00C2FF', fontSize: 10, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>
              {page === 2 ? '🚨 Risk Escalation Zone' : '⚠ AI Anomaly Zone'}
            </span>
          </div>

          {/* Right vignette */}
          <div style={{ position: 'absolute', top: 0, right: 0, width: 60, bottom: 0, background: 'linear-gradient(to right, transparent, rgba(11,18,32,0.55))', pointerEvents: 'none', zIndex: 3 }} />
        </div>

        {/* Watchlist */}
        <div style={{ width: 168, background: '#1a2236', borderLeft: '1px solid #252d3d', display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'hidden' }}>
          <div style={{ padding: '8px 10px 6px', borderBottom: '1px solid #252d3d', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ color: '#9ca3af', fontSize: 11, fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>Watchlist</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <span style={{ color: '#4a5568', fontSize: 11, cursor: 'default' }}>+</span>
              <span style={{ color: '#4a5568', fontSize: 11, cursor: 'default' }}>⋯</span>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', borderBottom: '1px solid #252d3d' }}>
            <span style={{ color: '#374151', fontSize: 9, fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Symbol</span>
            <span style={{ color: '#374151', fontSize: 9, fontFamily: 'Inter, sans-serif', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Chg%</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {watchlist.map((item) => (
              <div key={item.sym} style={{ padding: '6px 8px', borderBottom: '1px solid rgba(37,45,61,0.5)', background: item.active ? 'rgba(41,98,255,0.08)' : 'transparent', borderLeft: item.active ? '2px solid #2962FF' : '2px solid transparent', cursor: 'default' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                  <span style={{ color: item.active ? '#e2e8f0' : '#9ca3af', fontSize: 11, fontFamily: 'JetBrains Mono, monospace', fontWeight: item.active ? 700 : 400 }}>
                    {item.sym.replace('USDT','')}<span style={{ color: '#374151', fontSize: 9 }}>/USDT</span>
                    {item.sym === 'AAVEUSDT' && page === 2 && <span style={{ marginLeft: 4, fontSize: 9, color: '#ef4444' }}>⚠</span>}
                  </span>
                  <span style={{ color: item.up ? '#26a69a' : '#ef5350', fontSize: 10, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>{item.chg}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: item.active ? '#d1d5db' : '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}>{item.price}</span>
                  <svg width="32" height="14" viewBox="0 0 32 14" fill="none">
                    <polyline points={item.up ? '0,12 6,10 12,8 18,6 24,4 32,2' : '0,2 6,4 12,6 18,9 24,11 32,13'} stroke={item.up ? '#26a69a' : '#ef5350'} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Timeframe bar */}
      <div style={{ height: 32, background: '#1a2236', borderTop: '1px solid #252d3d', display: 'flex', alignItems: 'center', padding: '0 0 0 44px', gap: 2, flexShrink: 0, zIndex: 10 }}>
        {TFS.map((tf) => (
          <span key={tf} style={{ color: tf === '1H' ? '#e2e8f0' : '#4a5568', fontSize: 11, padding: '3px 8px', borderRadius: 4, background: tf === '1H' ? '#2962FF22' : 'transparent', border: tf === '1H' ? '1px solid rgba(41,98,255,0.4)' : '1px solid transparent', fontFamily: 'Inter, sans-serif', cursor: 'default' }}>{tf}</span>
        ))}
        <div style={{ width: 1, height: 18, background: '#252d3d', margin: '0 6px' }} />
        <span style={{ color: '#6b7280', fontSize: 11, padding: '3px 8px', cursor: 'default', fontFamily: 'Inter, sans-serif' }}>Indicators</span>
        <span style={{ color: '#6b7280', fontSize: 11, padding: '3px 8px', cursor: 'default', fontFamily: 'Inter, sans-serif' }}>Strategies</span>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 10px', marginRight: 172, background: page === 2 ? 'rgba(239,68,68,0.1)' : 'rgba(0,194,255,0.08)', border: `1px solid ${page === 2 ? 'rgba(239,68,68,0.3)' : 'rgba(0,194,255,0.25)'}`, borderRadius: 5 }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: page === 2 ? '#ef4444' : '#22c55e', boxShadow: `0 0 5px ${page === 2 ? '#ef4444' : '#22c55e'}`, animation: 'blink-dot 1s ease-in-out infinite' }} />
          <span style={{ color: page === 2 ? '#ef4444' : '#00C2FF', fontSize: 10, fontFamily: 'Outfit, sans-serif', fontWeight: 600 }}>
            {page === 2 ? 'QuantumRadar · Early Warning' : 'QuantumRadar Active'}
          </span>
        </div>
      </div>
    </div>
  )
}
