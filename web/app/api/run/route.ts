import { NextResponse } from "next/server";
import { runMock } from "@/lib/orchestrator";
import { DEFAULT_TEAM } from "@/lib/agents";
import type { Mission, RunResponse } from "@/lib/types";

// Vercel: keep this on the Node runtime; give it headroom for the proxy hop.
export const runtime = "nodejs";
export const maxDuration = 60;

/**
 * POST /api/run
 *
 * If AIROD_API_URL is set, proxy the mission to the Python backend on Railway
 * (real models, persistent memory, no timeout). Otherwise run the instant mock
 * so the dashboard works with zero configuration.
 */
export async function POST(req: Request) {
  let mission: Mission;
  try {
    const body = await req.json();
    mission = {
      title: String(body.title ?? "Untitled mission"),
      goal: String(body.goal ?? ""),
      rounds: Number(body.rounds ?? 3),
    };
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  const backend = process.env.AIROD_API_URL;

  if (backend) {
    try {
      const res = await fetch(`${backend.replace(/\/$/, "")}/run`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(mission),
        // Railway handles the long run; the browser sees one request.
        signal: AbortSignal.timeout(55_000),
      });
      if (!res.ok) throw new Error(`backend ${res.status}`);
      const data = (await res.json()) as RunResponse;
      return NextResponse.json(data);
    } catch (err) {
      // Fall back to the mock so the UI never dead-ends, but say what happened.
      const fallback = runMock(mission);
      fallback.warning =
        "Live backend unreachable — showing the mock run instead. " +
        `(${err instanceof Error ? err.message : "unknown error"})`;
      return NextResponse.json(fallback);
    }
  }

  const result = runMock(mission);
  result.agents = DEFAULT_TEAM;
  return NextResponse.json(result);
}
