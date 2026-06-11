import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.post("/seed")


def test_segment_preview_lapsed_sms():
    response = client.post("/segments/preview", json={"rules": {"channel": "sms", "min_last_order_days_ago": 60}})
    assert response.status_code == 200
    ids = sorted(customer["id"] for customer in response.json()["audience"])
    assert ids == ["cus_009", "cus_012"]


def test_agent_plan_is_structured():
    response = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers after 60 days"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_run_id"]
    assert payload["plan"]["requires_approval"] is True
    assert payload["plan"]["recommended_channel"] == "sms"


def test_campaign_requires_approval_before_send():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()
    response = client.post(f"/campaigns/{campaign['id']}/send")
    assert response.status_code == 409


def test_receipts_are_idempotent_and_order_safe():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    communication = models.Communication(
        id="msg_test",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="sent",
    )
    db.add(communication)
    db.commit()
    db.close()

    read = {"event_id": "evt_read", "communication_id": "msg_test", "campaign_id": campaign["id"], "customer_id": "cus_009", "status": "read"}
    opened = {"event_id": "evt_opened", "communication_id": "msg_test", "campaign_id": campaign["id"], "customer_id": "cus_009", "status": "opened"}
    assert client.post("/receipts", json=read).json()["accepted"] is True
    assert client.post("/receipts", json=read).json()["accepted"] is False
    assert client.post("/receipts", json=opened).json()["status"] == "read"


def test_invalid_segment_rules_are_rejected():
    response = client.post("/segments/preview", json={"rules": {"channel": "push", "min_last_order_days_ago": 10}})
    assert response.status_code == 422


def test_receipt_rejects_mismatched_customer_and_completes_campaign():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    db_campaign = db.get(models.Campaign, campaign["id"])
    db_campaign.status = models.CampaignStatus.sending.value
    communication = models.Communication(
        id="msg_complete",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="sent",
    )
    db.add(communication)
    db.commit()
    db.close()

    mismatch = {
        "event_id": "evt_bad_customer",
        "communication_id": "msg_complete",
        "campaign_id": campaign["id"],
        "customer_id": "cus_012",
        "status": "read",
    }
    assert client.post("/receipts", json=mismatch).json()["reason"] == "customer_mismatch"

    receipt = {
        "event_id": "evt_complete",
        "communication_id": "msg_complete",
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "status": "read",
    }
    assert client.post("/receipts", json=receipt).json()["accepted"] is True
    assert client.get(f"/campaigns/{campaign['id']}").json()["status"] == "completed"
