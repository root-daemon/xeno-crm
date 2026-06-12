import { Queue } from "bullmq";
import IORedis from "ioredis";

// REDIS_URL (e.g. rediss://... from Upstash) takes priority over host/port
export const connection = process.env.REDIS_URL
  ? new IORedis(process.env.REDIS_URL, { maxRetriesPerRequest: null })
  : new IORedis({
      host: process.env.REDIS_HOST ?? "localhost",
      port: Number(process.env.REDIS_PORT ?? 6379),
      maxRetriesPerRequest: null,
    });

export const campaignQueue = new Queue("campaign.send", { connection });
export const channelQueue = new Queue("channel.deliver", { connection });
