from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base
from .time import utc_now


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


JsonType = JSON().with_variant(JSONB, "postgresql")


class CampaignStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    queued = "queued"
    sending = "sending"
    completed = "completed"


class CommunicationStatus(str, Enum):
    queued = "queued"
    accepted = "accepted"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    read = "read"
    clicked = "clicked"
    converted = "converted"
    failed = "failed"


TERMINAL_COMMUNICATION_STATUSES = {
    CommunicationStatus.read.value,
    CommunicationStatus.clicked.value,
    CommunicationStatus.converted.value,
    CommunicationStatus.failed.value,
}


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("cus"))
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(180))
    city: Mapped[str] = mapped_column(String(80))
    gender: Mapped[str] = mapped_column(String(40), default="unknown")
    loyalty_tier: Mapped[str] = mapped_column(String(40), default="bronze")
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    rcs_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    global_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    unsubscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_days_ago: Mapped[int] = mapped_column(Integer, default=0)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("ord"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    total: Mapped[float] = mapped_column(Float)
    items: Mapped[list[str]] = mapped_column(JsonType, default=list)
    channel: Mapped[str] = mapped_column(String(40))
    days_ago: Mapped[int] = mapped_column(Integer)
    attributed_communication_id: Mapped[Optional[str]] = mapped_column(ForeignKey("communications.id"), nullable=True)
    attributed_campaign_id: Mapped[Optional[str]] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    attributed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    customer: Mapped[Customer] = relationship(back_populates="orders")


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("seg"))
    name: Mapped[str] = mapped_column(String(160))
    rules: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("run"))
    prompt: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    tool_calls: Mapped[list[dict]] = mapped_column(JsonType, default=list)
    final_recommendation: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("cmp"))
    agent_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(180))
    goal: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(40))
    segment_rules: Mapped[dict] = mapped_column(JsonType, default=dict)
    message_template: Mapped[str] = mapped_column(Text)
    approved_plan: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(40), default=CampaignStatus.draft.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    communications: Mapped[list["Communication"]] = relationship(back_populates="campaign")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("apr"))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    approved_by: Mapped[str] = mapped_column(String(120), default="demo.marketer@brand.test")
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Communication(Base):
    __tablename__ = "communications"
    __table_args__ = (UniqueConstraint("campaign_id", "customer_id", name="uq_campaign_customer"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("msg"))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[dict] = mapped_column(JsonType, default=dict)
    message: Mapped[str] = mapped_column(Text)
    variant_label: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    channel_priority: Mapped[list[str]] = mapped_column(JsonType, default=list)
    fallback_of_communication_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default=CommunicationStatus.queued.value)
    attributed_revenue: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    campaign: Mapped[Campaign] = relationship(back_populates="communications")
    events: Mapped[list["CommunicationEvent"]] = relationship(back_populates="communication")


class CommunicationEvent(Base):
    __tablename__ = "communication_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid("evt"))
    event_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    communication_id: Mapped[str] = mapped_column(ForeignKey("communications.id"))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[str] = mapped_column(String(40))
    metadata_json: Mapped[dict] = mapped_column(JsonType, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    communication: Mapped[Communication] = relationship(back_populates="events")
