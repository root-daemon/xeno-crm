"use client";

import { useEffect, useMemo, useState } from "react";
import { Send } from "lucide-react";
import { CLIENT_API_BASE, Performance } from "../../../lib/api";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function CampaignPerformanceView({ initialPerformance, initialInsights }: { initialPerformance: Performance; initialInsights: string[] }) {
  const [performance, setPerformance] = useState(initialPerformance);
  const [insights, setInsights] = useState(initialInsights);
  const [status, setStatus] = useState("");

  useEffect(() => {
    const interval = window.setInterval(async () => {
      const [nextPerformance, nextInsights] = await Promise.all([
        fetch(`${CLIENT_API_BASE}/campaigns/${initialPerformance.campaign.id}/performance`).then((response) => response.json()),
        fetch(`${CLIENT_API_BASE}/campaigns/${initialPerformance.campaign.id}/insights`).then((response) => response.json()),
      ]);
      setPerformance(nextPerformance);
      setInsights(nextInsights.insights ?? []);
    }, 2000);

    return () => window.clearInterval(interval);
  }, [initialPerformance.campaign.id]);

  const funnel = useMemo(() => [
    { label: "Sent", value: performance.counts.sent ?? 0 },
    { label: "Delivered", value: performance.counts.delivered ?? 0 },
    { label: "Opened", value: Math.max(performance.counts.opened ?? 0, performance.counts.read ?? 0) },
    { label: "Clicked", value: performance.counts.clicked ?? 0 },
    { label: "Purchased", value: performance.counts.purchased ?? performance.counts.converted ?? 0 },
  ], [performance]);
  const max = Math.max(...funnel.map((item) => item.value), performance.audience_size, 1);
  const canProcess = ["approved", "queued"].includes(performance.campaign.status)
    && performance.audience_size > 0
    && (performance.counts.accepted ?? 0) === 0
    && (performance.counts.sent ?? 0) === 0;

  async function processCampaign() {
    setStatus("Processing campaign through fake channel service...");
    const response = await fetch(`${CLIENT_API_BASE}/campaigns/${performance.campaign.id}/send`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    });
    if (!response.ok) {
      setStatus("Processing failed. Restart API, worker, Postgres, and Redis together, then try again.");
      return;
    }
    const nextPerformance = await fetch(`${CLIENT_API_BASE}/campaigns/${performance.campaign.id}/performance`).then((item) => item.json());
    setPerformance(nextPerformance);
    setStatus("Campaign is processing. Metrics will update automatically.");
  }

  return (
    <>
      <div className="topline">
        <div>
          <h1>{performance.campaign.name}</h1>
          <p className="muted">{performance.campaign.status} · {performance.campaign.channel.toUpperCase()} · {performance.campaign.goal}</p>
          {status ? <p className="muted">{status}</p> : null}
        </div>
        {canProcess ? (
          <button className="button" onClick={processCampaign}>
            <Send size={18} />Process Campaign
          </button>
        ) : null}
      </div>
      <section className="grid four fade-stack">
        <Metric label="Audience" value={performance.audience_size} />
        <Metric label="Accepted" value={performance.counts.accepted ?? 0} />
        <Metric label="Sent" value={performance.counts.sent ?? 0} />
        <Metric label="Delivered" value={performance.counts.delivered ?? 0} />
        <Metric label="Opened" value={performance.counts.opened ?? 0} />
        <Metric label="Clicked" value={performance.counts.clicked ?? 0} />
        <Metric label="Purchased" value={performance.counts.purchased ?? 0} />
        <Metric label="Failed" value={performance.counts.failed ?? 0} />
        <Metric label="Revenue" value={money.format(performance.revenue)} />
      </section>
      <div className="grid two section-gap">
        <section className="panel">
          <h2>Funnel View</h2>
          <div className="funnel">
            {funnel.map((item) => (
              <div className="funnel-step" key={item.label}>
                <strong>{item.label}</strong>
                <div className="funnel-bar">
                  <div className="funnel-fill" style={{ width: `${Math.max(3, (item.value / max) * 100)}%` }} />
                </div>
                <span>{item.value}</span>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <h2>AI Analytics</h2>
          <div className="split-list">
            {insights.map((insight) => (
              <div className="row" key={insight}>{insight}</div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}
