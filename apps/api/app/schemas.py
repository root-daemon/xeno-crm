from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Channel = Literal["whatsapp", "sms", "email", "rcs"]
OrderChannel = Literal["store", "online", "whatsapp", "sms", "email", "rcs"]
CommunicationStatusValue = Literal["queued", "accepted", "sent", "delivered", "opened", "read", "clicked", "converted", "failed"]


class CustomerIn(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=1, max_length=40)
    email: str = Field(min_length=3, max_length=180)
    city: str = Field(min_length=1, max_length=80)
    gender: str = "unknown"
    loyalty_tier: str = "bronze"
    tags: list[str] = Field(default_factory=list)
    whatsapp_opt_in: bool = True
    sms_opt_in: bool = True
    email_opt_in: bool = True
    rcs_opt_in: bool = False
    last_active_days_ago: int = Field(default=0, ge=0)


class OrderIn(BaseModel):
    id: Optional[str] = None
    customer_id: str = Field(min_length=1)
    total: float = Field(ge=0)
    items: list[str] = Field(default_factory=list)
    channel: OrderChannel
    days_ago: int = Field(ge=0)


class CustomerOut(CustomerIn):
    id: str
    order_count: int = 0
    lifetime_value: float = 0
    last_order_days_ago: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SegmentRules(BaseModel):
    channel: Optional[Channel] = None
    city: Optional[str] = None
    loyalty_tier: Optional[str] = None
    min_lifetime_value: Optional[float] = Field(default=None, ge=0)
    min_last_order_days_ago: Optional[int] = Field(default=None, ge=0)
    max_last_order_days_ago: Optional[int] = Field(default=None, ge=0)
    tag: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_last_order_window(self) -> "SegmentRules":
        if (
            self.min_last_order_days_ago is not None
            and self.max_last_order_days_ago is not None
            and self.min_last_order_days_ago > self.max_last_order_days_ago
        ):
            raise ValueError("min_last_order_days_ago cannot exceed max_last_order_days_ago")
        return self


class SegmentPreviewRequest(BaseModel):
    rules: SegmentRules = Field(default_factory=SegmentRules)


class SegmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    rules: SegmentRules = Field(default_factory=SegmentRules)


class AgentPlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)
    model: Optional[str] = Field(default=None, max_length=160)


class SegmentFromPromptRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    model: Optional[str] = Field(default=None, max_length=160)


class CampaignCreateRequest(BaseModel):
    agent_run_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=180)
    goal: str = Field(min_length=3)
    channel: Channel
    segment_rules: SegmentRules
    message_template: str = Field(min_length=1)
    approved_plan: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_channel_matches_segment(self) -> "CampaignCreateRequest":
        if self.segment_rules.channel and self.segment_rules.channel != self.channel:
            raise ValueError("campaign channel must match segment_rules.channel")
        return self


class ReceiptIn(BaseModel):
    event_id: Optional[str] = Field(default=None, min_length=1)
    communication_id: Optional[str] = Field(default=None, min_length=1)
    campaign_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    status: CommunicationStatusValue
    occurred_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if not normalized.get("communication_id"):
            normalized["communication_id"] = normalized.get("providerMessageId") or normalized.get("provider_message_id")
        if not normalized.get("occurred_at") and normalized.get("timestamp"):
            normalized["occurred_at"] = normalized["timestamp"]
        return normalized

    @model_validator(mode="after")
    def fill_provider_style_fields(self) -> "ReceiptIn":
        if not self.communication_id:
            raise ValueError("communication_id or providerMessageId is required")
        if not self.event_id:
            self.event_id = f"{self.communication_id}_{self.status}"
        return self
