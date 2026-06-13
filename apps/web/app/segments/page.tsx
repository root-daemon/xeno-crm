import Link from "next/link";
import { api, Segment } from "../../lib/api";
import { SegmentBuilder } from "./segment-builder";

export default async function SegmentsPage() {
  let segments: Segment[] = [];
  try {
    segments = await api<Segment[]>("/segments");
  } catch {
    segments = [];
  }

  return (
    <>
      <div className="topline">
        <div>
          <h1>Segments</h1>
          <p className="muted">Build, preview, and save audiences for campaign targeting.</p>
        </div>
        <Link className="button secondary" href="/campaigns/new">Create Campaign</Link>
      </div>
      <SegmentBuilder initialSegments={segments} />
    </>
  );
}
