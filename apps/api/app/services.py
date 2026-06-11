from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .seed import CUSTOMERS, ORDERS
from .time import utc_now

STATUS_RANK = {
    "queued": 0,
    "sent": 1,
    "delivered": 2,
    "opened": 3,
    "read": 4,
    "clicked": 5,
    "converted": 6,
    "failed": 99,
}


def seed_demo_data(db: Session) -> dict[str, int]:
    for item in CUSTOMERS:
        if not db.get(models.Customer, item["id"]):
            db.add(models.Customer(**item))
    for item in ORDERS:
        if not db.get(models.Order, item["id"]):
            db.add(models.Order(**item))
    db.commit()
    return {"customers": len(CUSTOMERS), "orders": len(ORDERS)}


def customer_rows(db: Session) -> list[dict[str, Any]]:
    customers = db.scalars(select(models.Customer)).all()
    rows = []
    for customer in customers:
        orders = list(customer.orders)
        rows.append({
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "city": customer.city,
            "gender": customer.gender,
            "loyalty_tier": customer.loyalty_tier,
            "tags": customer.tags,
            "whatsapp_opt_in": customer.whatsapp_opt_in,
            "sms_opt_in": customer.sms_opt_in,
            "email_opt_in": customer.email_opt_in,
            "rcs_opt_in": customer.rcs_opt_in,
            "last_active_days_ago": customer.last_active_days_ago,
            "order_count": len(orders),
            "lifetime_value": sum(order.total for order in orders),
            "last_order_days_ago": min([order.days_ago for order in orders], default=None),
        })
    return rows


def preview_segment(db: Session, rules: dict[str, Any]) -> list[dict[str, Any]]:
    rows = customer_rows(db)
    channel = rules.get("channel")
    matched = []
    for row in rows:
        if channel and not row.get(f"{channel}_opt_in"):
            continue
        if rules.get("city") and row["city"] != rules["city"]:
            continue
        if rules.get("loyalty_tier") and row["loyalty_tier"] != rules["loyalty_tier"]:
            continue
        if rules.get("min_lifetime_value") and row["lifetime_value"] < float(rules["min_lifetime_value"]):
            continue
        if rules.get("max_last_order_days_ago") and (row["last_order_days_ago"] is None or row["last_order_days_ago"] > int(rules["max_last_order_days_ago"])):
            continue
        if rules.get("min_last_order_days_ago") and (row["last_order_days_ago"] is None or row["last_order_days_ago"] < int(rules["min_last_order_days_ago"])):
            continue
        if rules.get("tag") and rules["tag"] not in row["tags"]:
            continue
        matched.append(row)
    return matched


def personalize(template: str, customer: models.Customer) -> str:
    return (
        template.replace("{{name}}", customer.name.split(" ")[0])
        .replace("{{city}}", customer.city)
        .replace("{{tier}}", customer.loyalty_tier)
    )


def performance(db: Session, campaign_id: str) -> dict[str, Any]:
    campaign = db.get(models.Campaign, campaign_id)
    communications = db.scalars(select(models.Communication).where(models.Communication.campaign_id == campaign_id)).all()
    counts = {key: 0 for key in ["queued", "sent", "delivered", "failed", "opened", "read", "clicked", "converted"]}
    for communication in communications:
        statuses = {event.status for event in communication.events}
        statuses.add(communication.status)
        for status in counts:
            if status in statuses:
                counts[status] += 1
    return {
        "campaign": campaign_to_dict(campaign) if campaign else None,
        "audience_size": len(communications) if communications else len(preview_segment(db, campaign.segment_rules)) if campaign else 0,
        "counts": counts,
        "revenue": sum(message.attributed_revenue for message in communications),
        "communications": [communication_to_dict(message) for message in communications],
    }


def apply_receipt(db: Session, receipt: dict[str, Any]) -> dict[str, Any]:
    existing = db.scalar(select(models.CommunicationEvent).where(models.CommunicationEvent.event_id == receipt["event_id"]))
    if existing:
        return {"accepted": False, "reason": "duplicate"}

    communication = db.get(models.Communication, receipt["communication_id"])
    if not communication:
        return {"accepted": False, "reason": "unknown_communication"}
    if communication.campaign_id != receipt["campaign_id"]:
        return {"accepted": False, "reason": "campaign_mismatch"}
    if communication.customer_id != receipt["customer_id"]:
        return {"accepted": False, "reason": "customer_mismatch"}

    event = models.CommunicationEvent(
        event_id=receipt["event_id"],
        communication_id=receipt["communication_id"],
        campaign_id=receipt["campaign_id"],
        customer_id=receipt["customer_id"],
        status=receipt["status"],
        metadata_json=receipt.get("metadata", {}),
        occurred_at=receipt.get("occurred_at") or utc_now(),
    )
    db.add(event)

    current_rank = STATUS_RANK.get(communication.status, 0)
    next_rank = STATUS_RANK.get(receipt["status"], 0)
    if receipt["status"] == "failed" or next_rank >= current_rank:
        communication.status = receipt["status"]
    if receipt["status"] == "converted":
        communication.attributed_revenue += float(receipt.get("metadata", {}).get("order_value", 0))
    reconcile_campaign_status(db, communication.campaign_id)
    db.commit()
    return {"accepted": True, "communication_id": communication.id, "status": communication.status}


def reconcile_campaign_status(db: Session, campaign_id: str) -> None:
    campaign = db.get(models.Campaign, campaign_id)
    if not campaign or campaign.status not in {models.CampaignStatus.queued.value, models.CampaignStatus.sending.value}:
        return

    communications = db.scalars(select(models.Communication).where(models.Communication.campaign_id == campaign_id)).all()
    if communications and all(message.status in models.TERMINAL_COMMUNICATION_STATUSES for message in communications):
        campaign.status = models.CampaignStatus.completed.value


def summary(db: Session) -> dict[str, Any]:
    customers = customer_rows(db)
    return {
        "totals": {
            "customers": len(customers),
            "orders": db.scalar(select(func.count(models.Order.id))) or 0,
            "campaigns": db.scalar(select(func.count(models.Campaign.id))) or 0,
            "communications": db.scalar(select(func.count(models.Communication.id))) or 0,
            "revenue": sum(row["lifetime_value"] for row in customers),
        },
        "recent_campaigns": [campaign_to_dict(campaign) for campaign in db.scalars(select(models.Campaign).order_by(models.Campaign.created_at.desc()).limit(5)).all()],
    }


def campaign_to_dict(campaign: models.Campaign) -> dict[str, Any]:
    return {
        "id": campaign.id,
        "agent_run_id": campaign.agent_run_id,
        "name": campaign.name,
        "goal": campaign.goal,
        "channel": campaign.channel,
        "segment_rules": campaign.segment_rules,
        "message_template": campaign.message_template,
        "approved_plan": campaign.approved_plan,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "approved_at": campaign.approved_at.isoformat() if campaign.approved_at else None,
        "queued_at": campaign.queued_at.isoformat() if campaign.queued_at else None,
    }


def communication_to_dict(communication: models.Communication) -> dict[str, Any]:
    return {
        "id": communication.id,
        "campaign_id": communication.campaign_id,
        "customer_id": communication.customer_id,
        "channel": communication.channel,
        "recipient": communication.recipient,
        "message": communication.message,
        "status": communication.status,
        "attributed_revenue": communication.attributed_revenue,
        "created_at": communication.created_at.isoformat() if communication.created_at else None,
    }
