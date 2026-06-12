import pg from "pg";

const connectionString = process.env.DATABASE_URL ?? "postgres://xeno:xeno@localhost:5432/xeno";
const isLocal = connectionString.includes("localhost") || connectionString.includes("127.0.0.1");

export const pool = new pg.Pool({
  connectionString,
  ssl: isLocal ? false : { rejectUnauthorized: false },
});

export async function query(text, params = []) {
  const result = await pool.query(text, params);
  return result.rows;
}
