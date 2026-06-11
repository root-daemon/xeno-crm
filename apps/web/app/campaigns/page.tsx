import Link from "next/link";
import { api, Campaign } from "../../lib/api";

export default async function CampaignsPage() {
  const campaigns = await api<Campaign[]>("/campaigns");
  return (
    <>
      <div className="topline">
        <div>
          <h1>Campaigns</h1>
          <p className="muted">Drafts, approvals, queued sends, and performance.</p>
        </div>
        <Link className="button" href="/campaigns/new">New Agent Campaign</Link>
      </div>
      <section className="grid">
        {campaigns.map((campaign) => (
          <Link className="row" href={`/campaigns/${campaign.id}`} key={campaign.id}>
            <strong>{campaign.name}</strong>
            <p className="muted">{campaign.status} · {campaign.channel.toUpperCase()} · {campaign.goal}</p>
          </Link>
        ))}
      </section>
    </>
  );
}
