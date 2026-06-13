import { AgentCampaignForm } from "./agent-campaign-form";
import { ManualCampaignForm } from "./manual-campaign-form";

export default async function NewCampaignPage({ searchParams }: { searchParams: Promise<{ goal?: string }> }) {
  const { goal } = await searchParams;
  return (
    <>
      <div className="topline">
        <div>
          <h1>AI Campaign Agent</h1>
          <p className="muted">Describe the goal. The agent plans; you approve before execution.</p>
        </div>
      </div>
      <AgentCampaignForm initialGoal={goal} />
      <div className="section-gap">
        <ManualCampaignForm />
      </div>
    </>
  );
}
