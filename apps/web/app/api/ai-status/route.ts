import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    openrouter: !!process.env.OPENROUTER_API_KEY,
  });
}
