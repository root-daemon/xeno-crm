import Link from "next/link";
import { api, Customer } from "../../../lib/api";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export default async function CustomerProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const customer = await api<Customer>(`/customers/${id}`);
  const orders = customer.purchase_history ?? [];

  return (
    <>
      <div className="topline">
        <div>
          <h1>{customer.name}</h1>
          <p className="muted">{customer.email} · {customer.phone} · {customer.city}</p>
        </div>
        <Link className="button secondary" href="/customers">Back to Customers</Link>
      </div>

      <section className="grid four">
        <Metric label="Orders" value={customer.order_count} />
        <Metric label="Total Spend" value={money.format(customer.lifetime_value)} />
        <Metric label="Last Purchase" value={customer.last_order_days_ago === null ? "No orders" : `${customer.last_order_days_ago} days ago`} />
        <Metric label="Tier" value={customer.loyalty_tier} />
      </section>

      <div className="grid two section-gap">
        <section className="panel">
          <h2>AI Customer Summary</h2>
          <p>{customer.ai_summary}</p>
          <div className="chips">
            {customer.tags.map((tag) => <span className="chip" key={tag}>{tag}</span>)}
          </div>
        </section>
        <section className="panel">
          <h2>Channel Opt-ins</h2>
          <div className="chips">
            <span className="chip">WhatsApp: {customer.whatsapp_opt_in ? "yes" : "no"}</span>
            <span className="chip">SMS: {customer.sms_opt_in ? "yes" : "no"}</span>
            <span className="chip">Email: {customer.email_opt_in ? "yes" : "no"}</span>
            <span className="chip">RCS: {customer.rcs_opt_in ? "yes" : "no"}</span>
          </div>
        </section>
      </div>

      <section className="panel section-gap">
        <h2>Purchase History</h2>
        <div className="split-list">
          {orders.length ? orders.map((order) => (
            <div className="row" key={order.id}>
              <strong>{money.format(order.total)} · {order.channel}</strong>
              <p className="muted">{order.days_ago} days ago · {order.items.join(", ")}</p>
            </div>
          )) : <p className="muted">No purchase history yet.</p>}
        </div>
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}
