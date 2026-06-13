"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Customer } from "../../lib/api";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function CustomerList({ customers }: { customers: Customer[] }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return customers;
    return customers.filter((customer) => {
      const haystack = [
        customer.name,
        customer.email,
        customer.city,
        customer.loyalty_tier,
        ...customer.tags,
      ].join(" ").toLowerCase();
      return haystack.includes(term);
    });
  }, [customers, query]);

  return (
    <section className="grid">
      <label>
        Search customers
        <div style={{ position: "relative" }}>
          <Search size={18} style={{ color: "var(--muted)", left: 12, position: "absolute", top: 12 }} />
          <input
            style={{ paddingLeft: 40 }}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name, email, city, or tag"
          />
        </div>
      </label>
      <div className="table">
        <div className="table-row header">
          <span>Name</span>
          <span>Email</span>
          <span>Orders</span>
          <span>Total Spend</span>
          <span>Last Order</span>
        </div>
        {filtered.map((customer) => (
          <Link className="table-row" href={`/customers/${customer.id}`} key={customer.id}>
            <span>
              <strong>{customer.name}</strong>
              <br />
              <span className="muted">{customer.city} · {customer.loyalty_tier}</span>
            </span>
            <span>{customer.email}</span>
            <span>{customer.order_count}</span>
            <span>{money.format(customer.lifetime_value)}</span>
            <span>{customer.last_order_days_ago === null ? "No orders" : `${customer.last_order_days_ago} days ago`}</span>
          </Link>
        ))}
      </div>
      {!filtered.length ? <p className="muted">No customers match that search.</p> : null}
    </section>
  );
}
