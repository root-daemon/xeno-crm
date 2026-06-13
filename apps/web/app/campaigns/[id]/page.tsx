import { api, Performance } from "../../../lib/api";
import { CampaignPerformanceView } from "./campaign-performance-view";

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const performance = await api<Performance>(`/campaigns/${id}/performance`);
  const insightPayload = await api<{ insights: string[] }>(`/campaigns/${id}/insights`);
  return <CampaignPerformanceView initialPerformance={performance} initialInsights={insightPayload.insights} />;
}
