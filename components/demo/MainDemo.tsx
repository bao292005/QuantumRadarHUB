"use client";

import { useState } from "react";
import CandlestickBacktest from "./CandlestickBacktest";
import ExtensionShell from "../extension/ExtensionShell";
import type { BacktestPoint } from "@/lib/types";

export default function MainDemo() {
  const [live, setLive] = useState<BacktestPoint | null>(null);
  return (
    <main className="demo-root">
      <CandlestickBacktest autoPlay syncReplay onPoint={setLive} initialFixture="luna_2022_05_09" />
      <div className="demo-panel"><ExtensionShell live={live} /></div>
    </main>
  );
}
