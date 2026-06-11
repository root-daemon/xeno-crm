import { api } from "../../../lib/api";

type Performance = {
  campaign: { id: string; name: string; status: string; channel: string; goal: string };
  audience_size: number;
  counts: Record<string, number>;
  revenue: number;
};

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const performance = await api<Performance>(`/campaigns/${id}/performance`);
  return (
    <>
      <div className="topline">
        <div>
          <h1>{performance.campaign.name}</h1>
          <p className="muted">{performance.campaign.status} · {performance.campaign.channel.toUpperCase()} · {performance.campaign.goal}</p>
        </div>
      </div>
      <section className="grid four">
        <Metric label="Audience" value={performance.audience_size} />
        <Metric label="Sent" value={performance.counts.sent ?? 0} />
        <Metric label="Delivered" value={performance.counts.delivered ?? 0} />
        <Metric label="Failed" value={performance.counts.failed ?? 0} />
        <Metric label="Opened" value={performance.counts.opened ?? 0} />
        <Metric label="Read" value={performance.counts.read ?? 0} />
        <Metric label="Clicked" value={performance.counts.clicked ?? 0} />
        <Metric label="Revenue" value={money.format(performance.revenue)} />
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}
