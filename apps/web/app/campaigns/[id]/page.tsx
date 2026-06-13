import { api, Performance } from "../../../lib/api";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const performance = await api<Performance>(`/campaigns/${id}/performance`);
  const insightPayload = await api<{ insights: string[] }>(`/campaigns/${id}/insights`);
  const funnel = [
    { label: "Sent", value: performance.counts.sent ?? 0 },
    { label: "Delivered", value: performance.counts.delivered ?? 0 },
    { label: "Opened", value: Math.max(performance.counts.opened ?? 0, performance.counts.read ?? 0) },
    { label: "Clicked", value: performance.counts.clicked ?? 0 },
    { label: "Purchased", value: performance.counts.purchased ?? performance.counts.converted ?? 0 },
  ];
  const max = Math.max(...funnel.map((item) => item.value), performance.audience_size, 1);

  return (
    <>
      <div className="topline">
        <div>
          <h1>{performance.campaign.name}</h1>
          <p className="muted">{performance.campaign.status} · {performance.campaign.channel.toUpperCase()} · {performance.campaign.goal}</p>
        </div>
      </div>
      <section className="grid four fade-stack">
        <Metric label="Audience" value={performance.audience_size} />
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
            {insightPayload.insights.map((insight) => (
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
