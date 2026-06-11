import { api, Customer } from "../../lib/api";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export default async function CustomersPage() {
  const customers = await api<Customer[]>("/customers");
  return (
    <>
      <div className="topline">
        <div>
          <h1>Customers</h1>
          <p className="muted">Shopper profiles enriched with order-derived attributes.</p>
        </div>
      </div>
      <section className="grid two">
        {customers.map((customer) => (
          <article className="row" key={customer.id}>
            <strong>{customer.name}</strong>
            <p className="muted">{customer.city} · {customer.loyalty_tier} · LTV {money.format(customer.lifetime_value)}</p>
            <div className="chips">{customer.tags.map((tag) => <span className="chip" key={tag}>{tag}</span>)}</div>
          </article>
        ))}
      </section>
    </>
  );
}
