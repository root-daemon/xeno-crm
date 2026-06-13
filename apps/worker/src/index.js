import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

// Load .env from the worker package root (dev convenience — no effect in prod)
try {
  const envPath = resolve(dirname(fileURLToPath(import.meta.url)), "..", ".env");
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const [key, ...rest] = trimmed.split("=");
    if (key && !(key in process.env)) process.env[key] = rest.join("=");
  }
} catch { /* .env is optional */ }

import express from "express";
import { Worker } from "bullmq";
import { campaignQueue, channelQueue, connection } from "./queues.js";
import { query } from "./db.js";
import { statusPlan } from "./lifecycle.js";

const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
const port = Number(process.env.PORT ?? process.env.WORKER_PORT ?? 9000);
const channelServiceUrl = process.env.CHANNEL_SERVICE_URL ?? `http://localhost:${port}`;

const app = express();
app.use(express.json());

app.get("/health", (_request, response) => response.json({ ok: true }));

app.post("/enqueue/campaign-send", async (request, response) => {
  const { campaign_id } = request.body;
  if (!campaign_id) return response.status(400).json({ error: "campaign_id required" });
  const job = await campaignQueue.add("campaign.send", { campaign_id }, {
    jobId: `campaign.send.${campaign_id}`,
    attempts: 3,
    backoff: { type: "exponential", delay: 500 }
  });
  response.status(202).json({ queued: true, job_id: job.id });
});

async function sendHandler(request, response) {
  const { campaignId, customerId, communicationId, recipient, channel, message, callbackUrl } = request.body;
  if (!campaignId || !customerId || !communicationId || !recipient || !channel || !message || !callbackUrl) {
    return response.status(400).json({
      error: "campaignId, customerId, communicationId, recipient, channel, message and callbackUrl are required"
    });
  }

  const providerMessageId = communicationId;
  scheduleChannelCallbacks({
    providerMessageId,
    communicationId,
    campaignId,
    customerId,
    callbackUrl
  });

  response.status(202).json({ providerMessageId, status: "accepted" });
}

app.post("/send", sendHandler);
app.post("/channel/send", sendHandler);

new Worker("campaign.send", async (job) => {
  const { campaign_id } = job.data;
  const [campaign] = await query("select * from campaigns where id = $1", [campaign_id]);
  if (!campaign) throw new Error(`Unknown campaign ${campaign_id}`);

  await query("update campaigns set status = $1 where id = $2", ["sending", campaign_id]);

  const audience = await query(audienceSql(campaign.segment_rules), audienceParams(campaign.segment_rules));
  for (const customer of audience) {
    const communicationId = `msg_${campaign_id}_${customer.id}`;
    const message = personalize(campaign.message_template, customer);
    await query(
      `insert into communications (id, campaign_id, customer_id, channel, recipient, message, status, attributed_revenue, created_at)
       values ($1, $2, $3, $4, $5::jsonb, $6, 'queued', 0, now())
       on conflict on constraint uq_campaign_customer do nothing`,
      [communicationId, campaign_id, customer.id, campaign.channel, JSON.stringify({ name: customer.name, phone: customer.phone, email: customer.email }), message]
    );
    const channelResponse = await fetch(`${channelServiceUrl}/send`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        campaignId: campaign_id,
        customerId: customer.id,
        communicationId,
        recipient: { name: customer.name, phone: customer.phone, email: customer.email },
        channel: campaign.channel,
        message,
        callbackUrl: `${apiBaseUrl}/receipts`
      })
    });
    if (!channelResponse.ok) throw new Error(`Channel send failed ${channelResponse.status}`);
  }
  return { created: audience.length };
}, { connection });

new Worker("channel.deliver", async (job) => {
  const [communication] = await query("select * from communications where id = $1", [job.data.communication_id]);
  if (!communication) throw new Error(`Unknown communication ${job.data.communication_id}`);

  for (const item of statusPlan(communication)) {
    await sleep(item.delay);
    const providerMessageId = job.data.provider_message_id ?? communication.id;
    const occurredAt = new Date().toISOString();
    const receipt = {
      event_id: `${communication.id}_${item.status}`,
      communication_id: communication.id,
      providerMessageId,
      campaign_id: communication.campaign_id,
      customer_id: communication.customer_id,
      status: item.status,
      occurred_at: occurredAt,
      timestamp: occurredAt,
      metadata: item.metadata ?? {}
    };
    const response = await fetch(job.data.callback_url ?? `${apiBaseUrl}/receipts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(receipt)
    });
    if (!response.ok) throw new Error(`Receipt failed ${response.status}`);
  }
}, { connection });

app.listen(port, () => {
  console.log(`Worker enqueue API listening on ${port}`);
});

function audienceSql(rules) {
  return `select c.*, coalesce(sum(o.total), 0) as lifetime_value, min(o.days_ago) as last_order_days_ago
          from customers c
          left join orders o on o.customer_id = c.id
          where ($1::text is null or c.city = $1::text)
            and (
              $6::text is null
              or ($6::text = 'whatsapp' and c.whatsapp_opt_in = true)
              or ($6::text = 'sms' and c.sms_opt_in = true)
              or ($6::text = 'email' and c.email_opt_in = true)
              or ($6::text = 'rcs' and c.rcs_opt_in = true)
            )
          group by c.id
          having ($2::float is null or coalesce(sum(o.total), 0) >= $2::float)
             and ($3::int is null or min(o.days_ago) >= $3::int)
             and ($4::int is null or min(o.days_ago) <= $4::int)
             and ($5::text is null or c.tags::jsonb ? $5::text)`;
}

function audienceParams(rules) {
  return [
    rules.city ?? null,
    rules.min_lifetime_value ?? null,
    rules.min_last_order_days_ago ?? null,
    rules.max_last_order_days_ago ?? null,
    rules.tag ?? null,
    rules.channel ?? null
  ];
}

function personalize(template, customer) {
  return template
    .replaceAll("{{name}}", customer.name.split(" ")[0])
    .replaceAll("{{city}}", customer.city)
    .replaceAll("{{tier}}", customer.loyalty_tier);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function scheduleChannelCallbacks({ providerMessageId, communicationId, campaignId, customerId, callbackUrl }) {
  let elapsed = 0;
  const plan = statusPlan({ id: communicationId, customer_id: customerId });
  for (const item of plan) {
    elapsed += item.delay;
    setTimeout(async () => {
      const occurredAt = new Date().toISOString();
      const receipt = {
        event_id: `${communicationId}_${item.status}`,
        communication_id: communicationId,
        providerMessageId,
        campaign_id: campaignId,
        customer_id: customerId,
        status: item.status,
        occurred_at: occurredAt,
        timestamp: occurredAt,
        metadata: item.metadata ?? {}
      };

      try {
        const callbackResponse = await fetch(callbackUrl, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(receipt)
        });
        if (!callbackResponse.ok) {
          console.error(`Receipt callback failed ${callbackResponse.status}`, receipt);
        }
      } catch (error) {
        console.error("Receipt callback failed", error);
      }
    }, elapsed);
  }
}
