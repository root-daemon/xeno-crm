import { api, Customer } from "../../lib/api";
import { CsvImporter } from "./csv-importer";
import { CustomerList } from "./customer-list";

export default async function CustomersPage() {
  let customers: Customer[];
  try {
    customers = await api<Customer[]>("/customers");
  } catch {
    customers = [];
  }

  return (
    <>
      <div className="topline">
        <div>
          <h1>Customers</h1>
          <p className="muted">Shopper profiles enriched with order-derived attributes.</p>
        </div>
      </div>
      <CsvImporter />
      <CustomerList customers={customers} />
    </>
  );
}
