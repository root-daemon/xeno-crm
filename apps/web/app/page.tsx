import Link from "next/link";
import { api, Summary } from "../lib/api";
import { SeedButton } from "./seed-button";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const defaultGoal = "Create a campaign to bring back shoppers who have not purchased in 60 days";

export default async function DashboardPage() {
  let summary: Summary;
  try {
    summary = await api<Summary>("/summary");
  } catch {
    summary = {
      totals: {
        customers: 0,
        orders: 0,
        campaigns: 0,
        active_segments: 0,
        campaigns_sent: 0,
        communications: 0,
        revenue: 0,
        revenue_generated: 0,
      },
      recommendations: {
        inactive_customers: 0,
        potential_recovery_revenue: 0,
        default_goal: defaultGoal,
      },
      recent_campaigns: [],
    };
  }
  summary = normalizeSummary(summary);

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
        <Metric label="Total Customers" value={summary.totals.customers} />
        <Metric label="Active Segments" value={summary.totals.active_segments} />
        <Metric label="Campaigns Sent" value={summary.totals.campaigns_sent} />
        <Metric label="Revenue Generated" value={money.format(summary.totals.revenue_generated)} />
      </section>
      <div className="grid two section-gap">
        <section className="panel">
          <h2>Recent Campaigns</h2>
          <div className="grid fade-stack">
            {summary.recent_campaigns.length ? summary.recent_campaigns.map((campaign) => (
              <Link className="row link-row" href={`/campaigns/${campaign.id}`} key={campaign.id}>
                <strong>{campaign.name}</strong>
                <p className="muted">{campaign.status} · {campaign.channel.toUpperCase()}</p>
              </Link>
            )) : <p className="muted">No campaigns yet. Create one from the AI Agent page.</p>}
          </div>
        </section>
        <section className="panel grid">
          <h2>AI Recommendations</h2>
          <div className="row">
            <strong>{summary.recommendations.inactive_customers} inactive customers</strong>
            <p className="muted">Potential recovery revenue: {money.format(summary.recommendations.potential_recovery_revenue)}</p>
            <p>Launch a winback campaign for shoppers who have not purchased in 60 days.</p>
          </div>
          <Link className="button" href={`/campaigns/new?goal=${encodeURIComponent(summary.recommendations.default_goal)}`}>Create Campaign</Link>
        </section>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function normalizeSummary(summary: Summary): Summary {
  return {
    totals: {
      customers: summary.totals?.customers ?? 0,
      orders: summary.totals?.orders ?? 0,
      campaigns: summary.totals?.campaigns ?? 0,
      active_segments: summary.totals?.active_segments ?? 0,
      campaigns_sent: summary.totals?.campaigns_sent ?? summary.totals?.campaigns ?? 0,
      communications: summary.totals?.communications ?? 0,
      revenue: summary.totals?.revenue ?? 0,
      revenue_generated: summary.totals?.revenue_generated ?? summary.totals?.revenue ?? 0,
    },
    recommendations: {
      inactive_customers: summary.recommendations?.inactive_customers ?? 0,
      potential_recovery_revenue: summary.recommendations?.potential_recovery_revenue ?? 0,
      default_goal: summary.recommendations?.default_goal ?? defaultGoal,
    },
    recent_campaigns: summary.recent_campaigns ?? [],
  };
}
