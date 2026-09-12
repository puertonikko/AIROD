import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 30;

/**
 * GET /api/status?jobId=... — proxy one poll to the Railway backend.
 * Fast (sub-second), so it never hits the serverless time limit no matter how
 * long the underlying run takes.
 */
export async function GET(req: Request) {
  const backend = process.env.AIROD_API_URL;
  const jobId = new URL(req.url).searchParams.get("jobId");

  if (!backend) {
    return NextResponse.json(
      { status: "error", detail: "No backend configured." },
      { status: 400 },
    );
  }
  if (!jobId) {
    return NextResponse.json(
      { status: "error", detail: "Missing jobId." },
      { status: 400 },
    );
  }

  try {
    const res = await fetch(`${backend.replace(/\/$/, "")}/run/status/${jobId}`, {
      signal: AbortSignal.timeout(20_000),
    });
    const j = await res.json();
    return NextResponse.json(j, { status: res.status });
  } catch (err) {
    // Transient network error — report as still running so the client retries.
    return NextResponse.json({
      status: "running",
      transient: err instanceof Error ? err.message : "network error",
    });
  }
}
