import { AgentCampaignForm } from "./agent-campaign-form";

export default function NewCampaignPage() {
  return (
    <>
      <div className="topline">
        <div>
          <h1>AI Campaign Agent</h1>
          <p className="muted">Describe the goal. The agent plans; you approve before execution.</p>
        </div>
      </div>
      <AgentCampaignForm />
    </>
  );
}
