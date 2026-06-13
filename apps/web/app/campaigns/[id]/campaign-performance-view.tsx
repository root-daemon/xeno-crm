"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, Send, Sparkles } from "lucide-react";
import { CampaignAnalysis, ChartItem, CLIENT_API_BASE, Performance } from "../../../lib/api";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("en-IN", { style: "percent", maximumFractionDigits: 0 });

export function CampaignPerformanceView({
  initialPerformance,
  initialInsights,
  initialAnalysis,
}: {
  initialPerformance: Performance;
  initialInsights: string[];
  initialAnalysis: CampaignAnalysis;
}) {
  const [performance, setPerformance] = useState(initialPerformance);
  const [insights, setInsights] = useState(initialInsights);
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [status, setStatus] = useState("");

  useEffect(() => {
    const interval = window.setInterval(async () => {
      const [nextPerformance, nextInsights, nextAnalysis] = await Promise.all([
        fetch(`${CLIENT_API_BASE}/campaigns/${initialPerformance.campaign.id}/performance`).then((response) => response.json()),
        fetch(`${CLIENT_API_BASE}/campaigns/${initialPerformance.campaign.id}/insights`).then((response) => response.json()),
        fetch(`${CLIENT_API_BASE}/campaigns/${initialPerformance.campaign.id}/analysis`).then((response) => response.json()),
      ]);
      setPerformance(nextPerformance);
      setInsights(nextInsights.insights ?? []);
      setAnalysis(nextAnalysis);
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
    const nextAnalysis = await fetch(`${CLIENT_API_BASE}/campaigns/${performance.campaign.id}/analysis`).then((item) => item.json());
    setPerformance(nextPerformance);
    setAnalysis(nextAnalysis);
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
          <BarList items={analysis.charts?.funnel?.length ? analysis.charts.funnel : funnel} max={max} />
        </section>
        <section className="panel">
          <h2>AI Post-Campaign Summary</h2>
          <div className="analysis-headline">
            <Sparkles size={18} />
            <strong>{analysis.summary?.headline ?? "Launch or send this campaign to generate post-campaign analysis."}</strong>
          </div>
          <div className="split-list">
            {(analysis.summary?.findings?.length ? analysis.summary.findings : insights).map((insight) => (
              <div className="row" key={insight}>{insight}</div>
            ))}
          </div>
        </section>
      </div>
      <div className="grid three section-gap">
        <section className="panel">
          <h2><AlertTriangle size={17} /> Failure Causes</h2>
          <BarList items={analysis.charts?.failure_reasons ?? []} empty="No failures recorded." />
        </section>
        <section className="panel">
          <h2><BarChart3 size={17} /> Failure by City</h2>
          <RateList items={analysis.charts?.failure_by_city ?? []} />
        </section>
        <section className="panel">
          <h2><BarChart3 size={17} /> Failure by Tier</h2>
          <RateList items={analysis.charts?.failure_by_loyalty_tier ?? []} />
        </section>
      </div>
      <div className="grid two section-gap">
        <section className="panel">
          <h2>Agent Next Actions</h2>
          <div className="split-list">
            {(analysis.summary?.next_actions ?? []).map((action) => (
              <div className="row" key={action}>{action}</div>
            ))}
          </div>
        </section>
        <section className="panel">
          <h2>Failed Recipient Examples</h2>
          {analysis.failure_examples?.length ? (
            <div className="failure-table">
              {analysis.failure_examples.map((example) => (
                <div className="failure-row" key={example.communication_id}>
                  <strong>{example.customer_name}</strong>
                  <span>{example.city} · {example.loyalty_tier}</span>
                  <span>{example.label}</span>
                  <span>{example.retryable ? "Retryable" : "Do not retry"}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No failed recipients for this campaign.</p>
          )}
        </section>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function BarList({ items, max, empty = "No data yet." }: { items: ChartItem[]; max?: number; empty?: string }) {
  const localMax = max ?? Math.max(...items.map((item) => item.value), 1);
  if (!items.length) return <p className="muted">{empty}</p>;
  return (
    <div className="funnel">
      {items.map((item) => (
        <div className="funnel-step" key={item.key ?? item.label}>
          <strong>{item.label}</strong>
          <div className="funnel-bar">
            <div className="funnel-fill" style={{ width: `${item.value ? Math.max(3, (item.value / localMax) * 100) : 0}%` }} />
          </div>
          <span>{item.value}</span>
        </div>
      ))}
    </div>
  );
}

function RateList({ items }: { items: ChartItem[] }) {
  if (!items.length) return <p className="muted">No segment failures recorded.</p>;
  return (
    <div className="rate-list">
      {items.slice(0, 6).map((item) => (
        <div className="rate-row" key={item.key ?? item.label}>
          <div>
            <strong>{item.label}</strong>
            <span>{item.value} of {item.total ?? 0} failed</span>
          </div>
          <div className="rate-track">
            <div className="rate-fill" style={{ width: `${Math.max(2, (item.rate ?? 0) * 100)}%` }} />
          </div>
          <span>{percent.format(item.rate ?? 0)}</span>
        </div>
      ))}
    </div>
  );
}
