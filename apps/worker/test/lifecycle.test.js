import test from "node:test";
import assert from "node:assert/strict";
import { statusPlan } from "../src/lifecycle.js";

test("channel lifecycle always starts with a terminal provider outcome path", () => {
  const events = statusPlan({ id: "msg_cmp_cus_009", customer_id: "cus_009" });
  assert.ok(events.length >= 1);
  assert.equal(events[0].status, "accepted");
  assert.ok(["sent", "failed"].includes(events[1].status));
});

test("failed lifecycle includes structured cause metadata", () => {
  const events = statusPlan({ id: "msg_failure_0", customer_id: "cus_035" });
  const failed = events.find((event) => event.status === "failed");
  assert.ok(failed);
  assert.ok(failed.metadata.reason);
  assert.ok(failed.metadata.stage);
  assert.equal(typeof failed.metadata.retryable, "boolean");
});

test("engagement lifecycle opens before read", () => {
  const events = statusPlan({ id: "msg_cmp_cus_009", customer_id: "cus_009" });
  const statuses = events.map((event) => event.status);
  assert.ok(statuses.indexOf("opened") < statuses.indexOf("read"));
});
