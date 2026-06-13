from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .seed import CAMPAIGNS, COMMUNICATIONS, CUSTOMERS, ORDERS, SEGMENTS
from .time import utc_now

STATUS_RANK = {
    "queued": 0,
    "accepted": 1,
    "sent": 2,
    "delivered": 3,
    "opened": 4,
    "read": 5,
    "clicked": 6,
    "converted": 7,
    "failed": 99,
}


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def seed_demo_data(db: Session) -> dict[str, int]:
    from datetime import timedelta, timezone

    for item in CUSTOMERS:
        if not db.get(models.Customer, item["id"]):
            db.add(models.Customer(**item))
    for item in ORDERS:
        if not db.get(models.Order, item["id"]):
            db.add(models.Order(**item))
    db.commit()

    for item in SEGMENTS:
        if db.get(models.Segment, item["id"]):
            continue
        db.add(models.Segment(**item))
    db.commit()

    for item in CAMPAIGNS:
        if db.get(models.Campaign, item["id"]):
            continue
        now = utc_now()
        created = now - timedelta(days=item["days_ago_created"])
        approved = (now - timedelta(days=item["days_ago_approved"])) if item["days_ago_approved"] else None
        campaign = models.Campaign(
            id=item["id"],
            name=item["name"],
            goal=item["goal"],
            channel=item["channel"],
            segment_rules=item["segment_rules"],
            message_template=item["message_template"],
            approved_plan=item["approved_plan"],
            status=item["status"],
            created_at=created,
            approved_at=approved,
            queued_at=approved,
        )
        db.add(campaign)
    db.commit()

    for item in COMMUNICATIONS:
        if db.get(models.Communication, item["id"]):
            continue
        db.add(models.Communication(
            id=item["id"],
            campaign_id=item["campaign_id"],
            customer_id=item["customer_id"],
            channel=item["channel"],
            recipient=item["recipient"],
            message=item["message"],
            status=item["status"],
            attributed_revenue=item["attributed_revenue"],
        ))
    db.commit()

    return {
        "customers": len(CUSTOMERS),
        "orders": len(ORDERS),
        "segments": len(SEGMENTS),
        "campaigns": len(CAMPAIGNS),
        "communications": len(COMMUNICATIONS),
    }


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


def customer_detail(db: Session, customer_id: str) -> dict[str, Any] | None:
    rows = customer_rows(db)
    customer = next((row for row in rows if row["id"] == customer_id), None)
    if not customer:
        return None

    orders = order_rows(db, customer_id)
    summary_text = ai_customer_summary(customer, orders)
    return {
        **customer,
        "purchase_history": orders,
        "ai_summary": summary_text,
    }


def order_rows(db: Session, customer_id: str) -> list[dict[str, Any]]:
    orders = db.scalars(
        select(models.Order)
        .where(models.Order.customer_id == customer_id)
        .order_by(models.Order.days_ago.asc())
    ).all()
    return [
        {
            "id": order.id,
            "customer_id": order.customer_id,
            "total": order.total,
            "items": order.items,
            "channel": order.channel,
            "days_ago": order.days_ago,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
        for order in orders
    ]


def ai_customer_summary(customer: dict[str, Any], orders: list[dict[str, Any]]) -> str:
    if not orders:
        return f"{customer['name']} has not purchased yet; start with a lightweight welcome campaign."

    cadence = "frequent" if customer["order_count"] >= 3 else "selective"
    value = "high-value" if customer["lifetime_value"] >= 7000 else "emerging"
    last_order = customer["last_order_days_ago"]
    inactivity = "recently active" if last_order is not None and last_order <= 30 else f"inactive for {last_order} days"
    top_tags = ", ".join(customer["tags"][:2]) if customer["tags"] else "general retail"
    return (
        f"{customer['name']} is a {value}, {cadence} {top_tags} shopper from {customer['city']} "
        f"who is {inactivity}. Best next step: a personalized {customer['loyalty_tier']} tier offer."
    )


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


def segment_to_dict(db: Session, segment: models.Segment) -> dict[str, Any]:
    rules = segment.rules or {}
    return {
        "id": segment.id,
        "name": segment.name,
        "rules": rules,
        "audience_size": len(preview_segment(db, rules)),
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
    }


def segment_rows(db: Session) -> list[dict[str, Any]]:
    segments = db.scalars(select(models.Segment).order_by(models.Segment.created_at.desc())).all()
    return [segment_to_dict(db, segment) for segment in segments]


def personalize(template: str, customer: models.Customer) -> str:
    return (
        template.replace("{{name}}", customer.name.split(" ")[0])
        .replace("{{city}}", customer.city)
        .replace("{{tier}}", customer.loyalty_tier)
    )


def performance(db: Session, campaign_id: str) -> dict[str, Any]:
    campaign = db.get(models.Campaign, campaign_id)
    communications = db.scalars(select(models.Communication).where(models.Communication.campaign_id == campaign_id)).all()
    counts = {key: 0 for key in ["queued", "accepted", "sent", "delivered", "failed", "opened", "read", "clicked", "converted"]}
    for communication in communications:
        statuses = {event.status for event in communication.events}
        statuses.add(communication.status)
        for status in counts:
            if status in statuses:
                counts[status] += 1
    counts["purchased"] = counts["converted"]
    return {
        "campaign": campaign_to_dict(campaign) if campaign else None,
        "audience_size": len(communications) if communications else len(preview_segment(db, campaign.segment_rules)) if campaign else 0,
        "counts": counts,
        "revenue": sum(message.attributed_revenue for message in communications),
        "communications": [communication_to_dict(message) for message in communications],
    }


def campaign_insights(db: Session, campaign_id: str) -> dict[str, Any]:
    campaign = db.get(models.Campaign, campaign_id)
    if not campaign:
        return {"insights": []}

    perf = performance(db, campaign_id)
    audience = preview_segment(db, campaign.segment_rules)
    counts = perf["counts"]
    sent = counts.get("sent", 0) or len(perf["communications"]) or len(audience)
    clicked = counts.get("clicked", 0)
    purchased = counts.get("purchased", 0)

    insights = []
    if sent:
        click_rate = clicked / sent
        purchase_rate = purchased / sent
        insights.append(f"{campaign.channel.upper()} click-through is {click_rate:.0%} with {clicked} clicked shoppers out of {sent} sent.")
        insights.append(f"Purchased conversion is {purchase_rate:.0%}; {purchased} shoppers generated attributed revenue of INR {perf['revenue']:,.0f}.")

    city_counts = count_by(audience, "city") if audience else {}
    if city_counts:
        top_city, top_count = max(city_counts.items(), key=lambda item: item[1])
        insights.append(f"{top_city} is the largest reachable city in this audience with {top_count} shoppers.")

    inactive_30_45 = sum(1 for row in audience if row["last_order_days_ago"] is not None and 30 <= row["last_order_days_ago"] <= 45)
    inactive_90_plus = sum(1 for row in audience if row["last_order_days_ago"] is not None and row["last_order_days_ago"] >= 90)
    if inactive_30_45 or inactive_90_plus:
        insights.append(f"Inactivity split: {inactive_30_45} shoppers are 30-45 days inactive and {inactive_90_plus} are 90+ days inactive.")

    if not insights:
        insights.append("Launch or send this campaign to generate channel and purchase insights.")
    return {"insights": insights}


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
    inactive_customers = [row for row in customers if (row["last_order_days_ago"] or 0) >= 60]
    active_segments = db.scalar(select(func.count(models.Segment.id))) or 0
    campaigns_sent = db.scalar(
        select(func.count(models.Campaign.id)).where(models.Campaign.status.in_([
            models.CampaignStatus.queued.value,
            models.CampaignStatus.sending.value,
            models.CampaignStatus.completed.value,
        ]))
    ) or 0
    recovery_revenue = sum(row["lifetime_value"] for row in inactive_customers) * 0.15
    return {
        "totals": {
            "customers": len(customers),
            "orders": db.scalar(select(func.count(models.Order.id))) or 0,
            "campaigns": db.scalar(select(func.count(models.Campaign.id))) or 0,
            "active_segments": active_segments,
            "campaigns_sent": campaigns_sent,
            "communications": db.scalar(select(func.count(models.Communication.id))) or 0,
            "revenue": sum(row["lifetime_value"] for row in customers),
            "revenue_generated": sum(row["lifetime_value"] for row in customers),
        },
        "recommendations": {
            "inactive_customers": len(inactive_customers),
            "potential_recovery_revenue": recovery_revenue,
            "default_goal": "Create a campaign to bring back shoppers who have not purchased in 60 days",
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
