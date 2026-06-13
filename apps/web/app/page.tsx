import Link from "next/link";
import { api, Summary } from "../lib/api";
import { SeedButton } from "./seed-button";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export default async function DashboardPage() {
  let summary: Summary;
  try {
    summary = await api<Summary>("/summary");
  } catch {
    summary = { totals: { customers: 0, orders: 0, campaigns: 0, communications: 0, revenue: 0 }, recent_campaigns: [] };
  }

  return (
    <>
      <div className="topline">
        <div>
          <h1>Campaign Cockpit</h1>
          <p className="muted">Agentic shopper engagement with approval-gated execution.</p>
        </div>
        <div className="actions">
          <SeedButton />
          <Link className="button" href="/campaigns/new">New Agent Campaign</Link>
        </div>
      </div>
      <section className="grid four fade-stack">
        <Metric label="Customers" value={summary.totals.customers} />
        <Metric label="Orders" value={summary.totals.orders} />
        <Metric label="Revenue" value={money.format(summary.totals.revenue)} />
        <Metric label="Messages" value={summary.totals.communications} />
      </section>
      <section className="panel section-gap">
        <h2>Recent Campaigns</h2>
        <div className="grid fade-stack">
          {summary.recent_campaigns.length ? summary.recent_campaigns.map((campaign) => (
            <Link className="row" href={`/campaigns/${campaign.id}`} key={campaign.id}>
              <strong>{campaign.name}</strong>
              <p className="muted">{campaign.status} · {campaign.channel.toUpperCase()}</p>
            </Link>
          )) : <p className="muted">No campaigns yet. Create one from the AI Agent page.</p>}
        </div>
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}
