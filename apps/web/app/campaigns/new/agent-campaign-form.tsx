"use client";

import { useEffect, useState } from "react";
import { CheckCircle, ExternalLink, Sparkles, Send } from "lucide-react";
import { CLIENT_API_BASE } from "../../../lib/api";
import { AI_MODELS, DEFAULT_MODEL_ID, SETTINGS_KEY } from "../../../lib/ai-models";

type PlanResponse = {
  agent_run_id: string | null;
  plan: {
    campaign_name: string;
    goal: string;
    recommended_channel: string;
    channel_priority?: string[];
    recommended_segment: { rules: Record<string, unknown>; reasoning: string };
    message_variants: { label: string; template: string }[];
    risk_notes: string[];
    expected_audience_size: number;
    model?: string;
  };
};

const REQUEST_TIMEOUT_MS = 5000;

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(err.error ?? `${path} failed`);
  }
  return response.json();
}

export function AgentCampaignForm({ initialGoal }: { initialGoal?: string }) {
  const [goal, setGoal] = useState(
    initialGoal || "Win back shoppers who have not purchased in 60 days with a personalized WhatsApp or SMS offer."
  );
  const [modelId, setModelId] = useState(DEFAULT_MODEL_ID);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [selectedVariantIndex, setSelectedVariantIndex] = useState(0);
  const [refineInstruction, setRefineInstruction] = useState("Make it punchier and prefer WhatsApp, then SMS fallback.");
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [isWorking, setIsWorking] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(SETTINGS_KEY);
    if (stored && AI_MODELS.find((m) => m.id === stored)) {
      setModelId(stored);
    }
  }, []);

  const selectedModel = AI_MODELS.find((m) => m.id === modelId) ?? AI_MODELS[0];

  async function generatePlan() {
    setIsWorking(true);
    setStatus("Thinking through audience, channel, and message...");
    setPlan(null);
    setCampaignId(null);
    try {
      const result = await post<PlanResponse>("/api/agent/campaign-plan", { goal, model: modelId });
      setPlan(result);
      setSelectedVariantIndex(0);
      setStatus("Plan ready. Review the agent decision and approve when ready.");
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsWorking(false);
    }
  }

  async function createDraft() {
    if (!plan) return;
    setIsWorking(true);
    setStatus("Creating draft campaign...");
    try {
      const selectedVariant = plan.plan.message_variants[selectedVariantIndex] ?? plan.plan.message_variants[0];
      const campaign = await post<{ id: string }>(`${CLIENT_API_BASE}/campaigns`, {
        agent_run_id: plan.agent_run_id ?? undefined,
        name: plan.plan.campaign_name,
        goal: plan.plan.goal,
        channel: plan.plan.recommended_channel,
        segment_rules: plan.plan.recommended_segment.rules,
        message_template: selectedVariant.template,
        approved_plan: { ...plan.plan, selected_message_variant: selectedVariant },
      });
      setCampaignId(campaign.id);
      setStatus("Draft created. Approval is required before sending.");
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsWorking(false);
    }
  }

  async function refinePlan() {
    if (!plan) return;
    setIsWorking(true);
    setStatus("Refining the plan with the agent...");
    try {
      const result = await post<PlanResponse>("/api/agent/campaign-plan/refine", {
        prior_plan: plan.plan,
        instruction: refineInstruction,
        model: modelId,
      });
      setPlan(result);
      setSelectedVariantIndex(0);
      setCampaignId(null);
      setStatus("Refined plan ready. Review it before creating the draft.");
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsWorking(false);
    }
  }

  async function approveAndSend() {
    if (!campaignId) return;
    setIsWorking(true);
    setStatus("Approving and queueing sends...");
    try {
      await post(`${CLIENT_API_BASE}/campaigns/${campaignId}/approve`);
      await post(`${CLIENT_API_BASE}/campaigns/${campaignId}/send`);
      setStatus("Approved and queued in BullMQ. Open the campaign page to watch callbacks.");
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div className="grid two">
      <section className="panel grid">
        <label>
          Campaign goal
          <textarea value={goal} onChange={(e) => setGoal(e.target.value)} disabled={isWorking} />
        </label>

        <label>
          AI Model
          <select
            value={modelId}
            onChange={(e) => {
              setModelId(e.target.value);
              localStorage.setItem(SETTINGS_KEY, e.target.value);
            }}
            disabled={isWorking}
            style={{ padding: "10px 11px", borderRadius: 6, border: "1px solid var(--line)", background: "white" }}
          >
            {AI_MODELS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label} — {m.description}
              </option>
            ))}
          </select>
        </label>

        <button className="button" disabled={isWorking || !goal.trim()} onClick={generatePlan}>
          <Sparkles size={18} />
          {isWorking ? "Working..." : "Generate Agent Plan"}
        </button>

        <p className="muted status-line">{status}</p>
      </section>

      <section className="panel">
        <h2>Agent Recommendation</h2>
        {plan ? (
          <div className="grid fade-stack">
            <div className="row">
              <strong>{plan.plan.campaign_name}</strong>
              <p className="muted">
                {plan.plan.recommended_channel.toUpperCase()} · {plan.plan.expected_audience_size} shoppers
              </p>
              {plan.plan.channel_priority?.length ? (
                <p className="muted">Fallback order: {plan.plan.channel_priority.map((item) => item.toUpperCase()).join(" -> ")}</p>
              ) : null}
              <p>{plan.plan.recommended_segment.reasoning}</p>
              {plan.plan.model && (
                <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
                  Generated by <strong>{selectedModel.label}</strong>
                </p>
              )}
            </div>
            <div className="row">
              <strong>Message</strong>
              <div className="variant-list">
                {plan.plan.message_variants.map((variant, index) => (
                  <button
                    type="button"
                    className={`variant-option ${index === selectedVariantIndex ? "active" : ""}`}
                    key={`${variant.label}-${index}`}
                    onClick={() => setSelectedVariantIndex(index)}
                    disabled={isWorking || !!campaignId}
                  >
                    <span>{variant.label}</span>
                    <strong>{variant.template}</strong>
                  </button>
                ))}
              </div>
            </div>
            <div className="chips">
              {plan.plan.risk_notes.map((note) => (
                <span className="chip" key={note}>{note}</span>
              ))}
            </div>
            <div className="row">
              <strong>Refine with Agent</strong>
              <textarea
                value={refineInstruction}
                onChange={(event) => setRefineInstruction(event.target.value)}
                disabled={isWorking || !!campaignId}
                style={{ marginTop: 8 }}
              />
              <button className="button secondary" disabled={isWorking || !!campaignId || !refineInstruction.trim()} onClick={refinePlan}>
                <Sparkles size={18} />Refine Plan
              </button>
            </div>
            <button className="button secondary" disabled={isWorking || !!campaignId} onClick={createDraft}>
              <CheckCircle size={18} />Create Draft
            </button>
            <button className="button" disabled={!campaignId || isWorking} onClick={approveAndSend}>
              <Send size={18} />Approve & Send
            </button>
            {campaignId && (
              <a className="button secondary" href={`/campaigns/${campaignId}`}>
                <ExternalLink size={18} />Open Campaign
              </a>
            )}
          </div>
        ) : (
          <p className="muted">Generate a plan to see the approval-gated recommendation.</p>
        )}
      </section>
    </div>
  );
}
