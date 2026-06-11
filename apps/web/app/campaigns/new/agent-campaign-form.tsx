"use client";

import { useState } from "react";
import { CheckCircle, Sparkles, Send } from "lucide-react";
import { CLIENT_API_BASE } from "../../../lib/api";

type PlanResponse = {
  agent_run_id: string;
  plan: {
    campaign_name: string;
    goal: string;
    recommended_channel: string;
    recommended_segment: { rules: Record<string, unknown>; reasoning: string };
    message_variants: { label: string; template: string }[];
    risk_notes: string[];
    expected_audience_size: number;
  };
};

export function AgentCampaignForm() {
  const [goal, setGoal] = useState("Win back shoppers who have not purchased in 60 days with a personalized WhatsApp or SMS offer.");
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");

  async function post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${CLIENT_API_BASE}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined
    });
    if (!response.ok) throw new Error(`${path} failed`);
    return response.json();
  }

  async function generatePlan() {
    setStatus("Thinking through audience, channel, and message...");
    const result = await post<PlanResponse>("/agent/campaign-plan", { goal });
    setPlan(result);
    setCampaignId(null);
    setStatus("Plan ready for review.");
  }

  async function createDraft() {
    if (!plan) return;
    const campaign = await post<{ id: string }>("/campaigns", {
      agent_run_id: plan.agent_run_id,
      name: plan.plan.campaign_name,
      goal: plan.plan.goal,
      channel: plan.plan.recommended_channel,
      segment_rules: plan.plan.recommended_segment.rules,
      message_template: plan.plan.message_variants[0].template,
      approved_plan: plan.plan
    });
    setCampaignId(campaign.id);
    setStatus("Draft created. Approval is required before sending.");
  }

  async function approveAndSend() {
    if (!campaignId) return;
    await post(`/campaigns/${campaignId}/approve`);
    await post(`/campaigns/${campaignId}/send`);
    setStatus("Approved and queued in BullMQ. Open the campaign page to watch callbacks.");
  }

  return (
    <div className="grid two">
      <section className="panel grid">
        <label>
          Campaign goal
          <textarea value={goal} onChange={(event) => setGoal(event.target.value)} />
        </label>
        <button className="button" onClick={generatePlan}><Sparkles size={18} />Generate Agent Plan</button>
        <p className="muted">{status}</p>
      </section>
      <section className="panel">
        <h2>Agent Recommendation</h2>
        {plan ? (
          <div className="grid">
            <div className="row">
              <strong>{plan.plan.campaign_name}</strong>
              <p className="muted">{plan.plan.recommended_channel.toUpperCase()} · {plan.plan.expected_audience_size} shoppers</p>
              <p>{plan.plan.recommended_segment.reasoning}</p>
            </div>
            <div className="row">
              <strong>Message</strong>
              <p>{plan.plan.message_variants[0].template}</p>
            </div>
            <div className="chips">{plan.plan.risk_notes.map((note) => <span className="chip" key={note}>{note}</span>)}</div>
            <button className="button secondary" onClick={createDraft}><CheckCircle size={18} />Create Draft</button>
            <button className="button" disabled={!campaignId} onClick={approveAndSend}><Send size={18} />Approve & Send</button>
            {campaignId ? <a className="button secondary" href={`/campaigns/${campaignId}`}>Open Campaign</a> : null}
          </div>
        ) : <p className="muted">Generate a plan to see the approval-gated recommendation.</p>}
      </section>
    </div>
  );
}
