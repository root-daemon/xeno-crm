from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .agent import build_campaign_plan
from .config import settings
from .database import get_db
from .migrations import run_migrations
from .schemas import AgentPlanRequest, CampaignCreateRequest, CustomerIn, OrderIn, ReceiptIn, SegmentCreateRequest, SegmentPreviewRequest
from .services import (
    apply_receipt,
    campaign_insights,
    campaign_to_dict,
    customer_detail,
    customer_rows,
    order_rows,
    performance,
    preview_segment,
    seed_demo_data,
    segment_rows,
    segment_to_dict,
    summary,
)
from .time import utc_now


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_migrations_on_startup:
        try:
            run_migrations()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Migration failed: {exc}") from exc
    yield


app = FastAPI(title="Xeno Agentic CRM API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/seed")
def seed(db: Session = Depends(get_db)) -> dict[str, int]:
    return seed_demo_data(db)


@app.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict:
    return summary(db)


@app.post("/ingest/customers")
def ingest_customers(payload: list[CustomerIn], db: Session = Depends(get_db)) -> dict:
    for item in payload:
        data = item.model_dump()
        customer_id = data.pop("id") or models.uid("cus")
        existing = db.get(models.Customer, customer_id)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            db.add(models.Customer(id=customer_id, **data))
    db.commit()
    return {"customers": customer_rows(db)}


@app.post("/ingest/orders")
def ingest_orders(payload: list[OrderIn], db: Session = Depends(get_db)) -> dict:
    for item in payload:
        data = item.model_dump()
        order_id = data.pop("id") or models.uid("ord")
        if not db.get(models.Customer, data["customer_id"]):
            raise HTTPException(status_code=422, detail=f"unknown customer_id: {data['customer_id']}")
        existing = db.get(models.Order, order_id)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            db.add(models.Order(id=order_id, **data))
    db.commit()
    return {"accepted": len(payload)}


@app.get("/customers")
def customers(db: Session = Depends(get_db)) -> list[dict]:
    return customer_rows(db)


@app.get("/customers/{customer_id}")
def customer(customer_id: str, db: Session = Depends(get_db)) -> dict:
    found = customer_detail(db, customer_id)
    if not found:
        raise HTTPException(status_code=404, detail="customer not found")
    return found


@app.get("/customers/{customer_id}/orders")
def customer_orders(customer_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if not db.get(models.Customer, customer_id):
        raise HTTPException(status_code=404, detail="customer not found")
    return order_rows(db, customer_id)


@app.get("/segments")
def segments(db: Session = Depends(get_db)) -> list[dict]:
    return segment_rows(db)


@app.post("/segments")
def create_segment(payload: SegmentCreateRequest, db: Session = Depends(get_db)) -> dict:
    segment = models.Segment(
        name=payload.name,
        rules=payload.rules.model_dump(exclude_none=True),
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return segment_to_dict(db, segment)


@app.post("/segments/preview")
def segment_preview(payload: SegmentPreviewRequest, db: Session = Depends(get_db)) -> dict:
    return {"audience": preview_segment(db, payload.rules.model_dump(exclude_none=True))}


@app.post("/agent/campaign-plan")
def campaign_plan(payload: AgentPlanRequest, db: Session = Depends(get_db)) -> dict:
    plan = build_campaign_plan(db, payload.goal)
    run = models.AgentRun(
        prompt=payload.goal,
        model=plan["model"],
        tool_calls=plan["tool_calls"],
        final_recommendation=plan,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"agent_run_id": run.id, "plan": plan}


@app.get("/agent/runs/{run_id}")
def agent_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.get(models.AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="agent run not found")
    return {
        "id": run.id,
        "prompt": run.prompt,
        "model": run.model,
        "tool_calls": run.tool_calls,
        "final_recommendation": run.final_recommendation,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@app.post("/campaigns")
def create_campaign(payload: CampaignCreateRequest, db: Session = Depends(get_db)) -> dict:
    if payload.agent_run_id and not db.get(models.AgentRun, payload.agent_run_id):
        raise HTTPException(status_code=422, detail="unknown agent_run_id")
    campaign = models.Campaign(
        agent_run_id=payload.agent_run_id,
        name=payload.name,
        goal=payload.goal,
        channel=payload.channel,
        segment_rules=payload.segment_rules.model_dump(exclude_none=True),
        message_template=payload.message_template,
        approved_plan=payload.approved_plan,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@app.get("/campaigns")
def campaigns(db: Session = Depends(get_db)) -> list[dict]:
    return [campaign_to_dict(item) for item in db.scalars(select(models.Campaign).order_by(models.Campaign.created_at.desc())).all()]


@app.get("/campaigns/{campaign_id}")
def campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    found = db.get(models.Campaign, campaign_id)
    if not found:
        raise HTTPException(status_code=404, detail="campaign not found")
    return campaign_to_dict(found)


@app.post("/campaigns/{campaign_id}/approve")
def approve_campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    campaign = db.get(models.Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    if campaign.status != models.CampaignStatus.draft.value:
        raise HTTPException(status_code=409, detail="only draft campaigns can be approved")
    campaign.status = models.CampaignStatus.approved.value
    campaign.approved_at = utc_now()
    db.add(models.Approval(campaign_id=campaign.id))
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@app.post("/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    campaign = db.get(models.Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    if campaign.status != models.CampaignStatus.approved.value:
        raise HTTPException(status_code=409, detail="campaign requires approval before send")

    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(f"{settings.worker_url}/enqueue/campaign-send", json={"campaign_id": campaign_id})
        response.raise_for_status()

    campaign.status = models.CampaignStatus.queued.value
    campaign.queued_at = utc_now()
    db.commit()
    return {"queued": True, "campaign_id": campaign_id}


@app.get("/campaigns/{campaign_id}/performance")
def campaign_performance(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(models.Campaign, campaign_id):
        raise HTTPException(status_code=404, detail="campaign not found")
    return performance(db, campaign_id)


@app.get("/campaigns/{campaign_id}/insights")
def get_campaign_insights(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(models.Campaign, campaign_id):
        raise HTTPException(status_code=404, detail="campaign not found")
    return campaign_insights(db, campaign_id)


@app.post("/receipts")
def receipts(payload: ReceiptIn, db: Session = Depends(get_db)) -> dict:
    return apply_receipt(db, payload.model_dump())
