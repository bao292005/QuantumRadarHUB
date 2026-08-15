import TradingViewMock from "@/components/demo/TradingViewMock";
import ExtensionShell from "@/components/extension/ExtensionShell";

export default function DemoPage() {
  return <main className="demo-root"><TradingViewMock /><div className="demo-panel"><ExtensionShell /></div></main>;
}
