export function statusPlan(communication) {
  const base = checksum(communication.id);
  if (base % 7 === 0) {
    return [
      { status: "accepted", delay: 20 },
      { status: "failed", delay: 400, metadata: { reason: "simulated_provider_reject" } }
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

function checksum(value) {
  return [...String(value)].reduce((sum, char) => sum + char.charCodeAt(0), 0);
}
