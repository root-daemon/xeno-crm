import pg from "pg";

const connectionString = process.env.DATABASE_URL ?? "postgres://xeno:xeno@localhost:5432/xeno";

// Decide whether to negotiate SSL. Managed Postgres (RDS, Upstash, etc.) needs
// it, but a local/Docker Postgres rejects it ("server does not support SSL").
// The old check only special-cased localhost, so the in-cluster host "postgres"
// wrongly tried SSL and every worker DB query failed.
function shouldUseSsl(cs) {
  if (process.env.DATABASE_SSL === "true") return true;
  if (process.env.DATABASE_SSL === "false") return false;
  if (/sslmode=require/i.test(cs)) return true;
  const host = (cs.match(/@([^:/?]+)/) ?? [])[1] ?? "";
  const isPrivateHost =
    ["localhost", "127.0.0.1", "postgres", "db", "::1"].includes(host) ||
    host.endsWith(".internal") ||
    host.endsWith(".local");
  // Public managed hosts default to SSL; private/in-cluster hosts do not.
  return !isPrivateHost;
}

export const pool = new pg.Pool({
  connectionString,
  ssl: shouldUseSsl(connectionString) ? { rejectUnauthorized: false } : false,
});

export async function query(text, params = []) {
  const result = await pool.query(text, params);
  return result.rows;
}
