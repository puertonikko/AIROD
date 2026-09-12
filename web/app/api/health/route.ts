import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 15;

/**
 * GET /api/health — is the live backend configured, reachable, and keyed?
 * Powers the header badge so it reflects real connectivity, not the last run.
 */
export async function GET() {
  const backend = process.env.AIROD_API_URL;
  if (!backend) return NextResponse.json({ configured: false });
  try {
    const res = await fetch(`${backend.replace(/\/$/, "")}/health`, {
      signal: AbortSignal.timeout(10_000),
    });
    const j = await res.json();
    return NextResponse.json({ configured: true, ok: !!j.ok, hasKey: !!j.hasKey });
  } catch (err) {
    return NextResponse.json({
      configured: true,
      ok: false,
      error: err instanceof Error ? err.message : "unreachable",
    });
  }
}
