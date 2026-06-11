import pg from "pg";

export const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL ?? "postgres://xeno:xeno@localhost:5432/xeno"
});

export async function query(text, params = []) {
  const result = await pool.query(text, params);
  return result.rows;
}
