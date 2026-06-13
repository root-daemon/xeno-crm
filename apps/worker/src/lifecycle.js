export function statusPlan(communication) {
  const base = checksum(communication.id);
  if (base % 7 === 0) {
    return [
      { status: "accepted", delay: 20 },
      { status: "failed", delay: 400, metadata: failureProfile(communication, base) }
    ];
  }

  const clicked = checksum(communication.customer_id) % 3 === 0;
  const converted = checksum(communication.customer_id) % 5 === 0;
  return [
    { status: "accepted", delay: 20 },
    { status: "sent", delay: 100 },
    { status: "delivered", delay: 350 },
    { status: "opened", delay: 650 },
    { status: "read", delay: 900 },
    ...(clicked ? [{ status: "clicked", delay: 1200, metadata: { url: "https://brand.example/edit" } }] : []),
    ...(converted ? [{ status: "converted", delay: 1600, metadata: { order_value: 2499 } }] : [])
  ];
}

function failureProfile(communication, base) {
  const profiles = [
    { reason: "provider_reject", stage: "provider_acceptance", retryable: true },
    { reason: "invalid_recipient", stage: "recipient_validation", retryable: false },
    { reason: "user_opted_out", stage: "consent_check", retryable: false },
    { reason: "throttled", stage: "provider_queue", retryable: true },
    { reason: "template_policy", stage: "template_review", retryable: false }
  ];
  return profiles[(base + checksum(communication.customer_id)) % profiles.length];
}

function checksum(value) {
  return [...String(value)].reduce((sum, char) => sum + char.charCodeAt(0), 0);
}
