import test from "node:test";
import assert from "node:assert/strict";
import { statusPlan } from "../src/lifecycle.js";

test("channel lifecycle always starts with a terminal provider outcome path", () => {
  const events = statusPlan({ id: "msg_cmp_cus_009", customer_id: "cus_009" });
  assert.ok(events.length >= 1);
  assert.ok(["sent", "failed"].includes(events[0].status));
});
