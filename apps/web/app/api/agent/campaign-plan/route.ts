import { NextRequest, NextResponse } from "next/server";
import { generateObject } from "ai";
import { createOpenRouter } from "@openrouter/ai-sdk-provider";
import { z } from "zod";
import { API_BASE } from "../../../../lib/api";
import { AI_MODELS, DEFAULT_MODEL_ID } from "../../../../lib/ai-models";

// Single gateway for every model. The key lives only in OPENROUTER_API_KEY.
const openrouter = createOpenRouter({ apiKey: process.env.OPENROUTER_API_KEY ?? "" });

// Only models we explicitly list are allowed — prevents a crafted request from
// selecting an arbitrary (expensive) slug and burning credits.
const ALLOWED_MODEL_IDS = new Set(AI_MODELS.map((m) => m.id));

function resolveModelId(requested: string | undefined): string {
  return requested && ALLOWED_MODEL_IDS.has(requested) ? requested : DEFAULT_MODEL_ID;
}

const ALLOWED_CHANNELS = ["whatsapp", "sms", "email", "rcs"] as const;

const campaignPlanSchema = z.object({
  campaign_name: z.string().describe("Short, memorable campaign name"),
  recommended_channel: z.enum(ALLOWED_CHANNELS).describe("Best channel based on opt-in data"),
  recommended_segment: z.object({
    rules: z.object({
      channel: z.enum(ALLOWED_CHANNELS).optional(),
      city: z.string().optional(),
      loyalty_tier: z.string().optional(),
      min_lifetime_value: z.number().optional(),
      min_last_order_days_ago: z.number().optional(),
      max_last_order_days_ago: z.number().optional(),
      tag: z.string().optional(),
    }),
    reasoning: z.string().describe("Why this segment was chosen"),
  }),
  message_variants: z.array(z.object({
    label: z.string(),
    template: z.string().describe("Use {{name}} as placeholder for customer name"),
  })).min(1).max(3),
  risk_notes: z.array(z.string()).max(5),
  expected_audience_size: z.number().int().describe("Estimated number of customers who match the segment"),
});

type CustomerRow = {
  id: string;
  name: string;
  city: string;
  loyalty_tier: string;
  tags: string[];
  lifetime_value: number;
  last_order_days_ago: number | null;
  whatsapp_opt_in?: boolean;
  sms_opt_in?: boolean;
  email_opt_in?: boolean;
  rcs_opt_in?: boolean;
};

type CampaignPlan = z.infer<typeof campaignPlanSchema>;

// Deterministic fallback so the demo never hard-fails when the LLM is
// unavailable (free-model 429s, exhausted credits, transient network errors).
// Mirrors the goal-keyword heuristics used by the Python agent fallback.
function buildLocalPlan(goal: string, summary: ReturnType<typeof buildCustomerSummary>): CampaignPlan {
  const g = goal.toLowerCase();
  const isWinback = /win|lapsed|inactive|churn|60 day/.test(g);
  const isPremium = /premium|vip|best|high value/.test(g);
  const isFestive = /festive|wedding|diwali|season/.test(g);

  let rules: CampaignPlan["recommended_segment"]["rules"];
  let name: string;
  let offer: string;
  if (isWinback) {
    rules = { channel: "sms", min_last_order_days_ago: 60 };
    name = "Lapsed Shopper Comeback";
    offer = "20% comeback reward";
  } else if (isPremium) {
    rules = { channel: "whatsapp", min_lifetime_value: 7000 };
    name = "VIP Early Access Drop";
    offer = "private early access";
  } else if (isFestive) {
    rules = { channel: "whatsapp", tag: "festive" };
    name = "Festive Shopper Activation";
    offer = "festive styling edit";
  } else {
    rules = { channel: "whatsapp", max_last_order_days_ago: 45 };
    name = "Recent Buyer Repeat Push";
    offer = "new arrivals edit";
  }

  return {
    campaign_name: name,
    recommended_channel: rules.channel ?? "whatsapp",
    recommended_segment: {
      rules,
      reasoning: `Heuristic match over ${summary.total} shopper profiles using behavioural and opt-in filters.`,
    },
    message_variants: [
      { label: "direct", template: `Hi {{name}}, we picked a ${offer} for you based on your last purchase. Use code XENO10 today.` },
      { label: "softer", template: `Hi {{name}}, your ${offer} is waiting. Explore a personalized edit picked for you.` },
    ],
    risk_notes: [
      "Requires marketer approval before send.",
      "Only opted-in shoppers are included in the segment.",
    ],
    expected_audience_size: isWinback ? summary.lapsed_60_days : isPremium ? summary.high_value_7000 : summary.total,
  };
}

function buildCustomerSummary(customers: CustomerRow[]) {
  const cities: Record<string, number> = {};
  const tiers: Record<string, number> = {};
  let lapsed = 0;
  let highValue = 0;
  const optIns = { whatsapp: 0, sms: 0, email: 0, rcs: 0 };

  for (const c of customers) {
    cities[c.city] = (cities[c.city] ?? 0) + 1;
    tiers[c.loyalty_tier] = (tiers[c.loyalty_tier] ?? 0) + 1;
    if ((c.last_order_days_ago ?? 0) >= 60) lapsed++;
    if (c.lifetime_value >= 7000) highValue++;
    if (c.whatsapp_opt_in) optIns.whatsapp++;
    if (c.sms_opt_in) optIns.sms++;
    if (c.email_opt_in) optIns.email++;
    if (c.rcs_opt_in) optIns.rcs++;
  }

  return { total: customers.length, cities, loyalty_tiers: tiers, lapsed_60_days: lapsed, high_value_7000: highValue, opt_ins: optIns };
}

export async function POST(req: NextRequest) {
  try {
    const { goal, model: requestedModel } = await req.json() as { goal: string; model?: string };

    if (!goal?.trim()) {
      return NextResponse.json({ error: "goal is required" }, { status: 400 });
    }
    if (!process.env.OPENROUTER_API_KEY) {
      return NextResponse.json({ error: "OPENROUTER_API_KEY is not configured" }, { status: 500 });
    }

    const modelId = resolveModelId(requestedModel);

    let customers: CustomerRow[] = [];
    try {
      const res = await fetch(`${API_BASE}/customers`, { cache: "no-store" });
      if (res.ok) customers = await res.json();
    } catch {
      // continue with empty customer list
    }

    const summary = buildCustomerSummary(customers);

    const systemPrompt = [
      "You are a CRM campaign planning agent for an Indian fashion brand.",
      "Analyse the customer data and craft a targeted campaign plan.",
      "Only use channels: whatsapp, sms, email, rcs.",
      "Segment rules may only use: channel, city, loyalty_tier, min_lifetime_value,",
      "min_last_order_days_ago, max_last_order_days_ago, tag.",
      "Always include 'Requires marketer approval before send.' in risk_notes.",
      "Use {{name}} as the placeholder for customer name in message templates.",
    ].join(" ");

    const userPrompt = JSON.stringify({
      goal,
      customer_summary: summary,
      instructions: "Return a campaign plan that best serves this goal.",
    });

    let plan: CampaignPlan;
    let usedModel = modelId;
    let toolResult: Record<string, unknown> = { status: "ok" };
    try {
      const { object } = await generateObject({
        model: openrouter(modelId),
        schema: campaignPlanSchema,
        system: systemPrompt,
        prompt: userPrompt,
        // Cap output so a runaway response can't rack up token cost on paid models.
        maxOutputTokens: 1200,
        temperature: 0.2,
      });
      plan = object;
    } catch (llmErr) {
      // Any LLM failure (429 rate-limit, exhausted credits, schema mismatch)
      // degrades to a deterministic plan rather than breaking the demo.
      const reason = llmErr instanceof Error ? llmErr.message : String(llmErr);
      console.warn(`[campaign-plan] LLM failed (${modelId}), using local fallback: ${reason}`);
      plan = buildLocalPlan(goal, summary);
      usedModel = `${modelId}-local-fallback`;
      toolResult = { status: "fallback", reason };
    }

    const fullPlan = {
      ...plan,
      goal,
      audience_insights: [],
      requires_approval: true,
      model: usedModel,
      tool_calls: [
        { tool: "generate_campaign_plan", provider: "openrouter", model: usedModel, result: toolResult },
      ],
    };

    return NextResponse.json({ agent_run_id: null, plan: fullPlan });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[campaign-plan]", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
