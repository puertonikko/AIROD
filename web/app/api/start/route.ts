import { NextResponse } from "next/server";
import { runMock } from "@/lib/orchestrator";
import { PRESETS } from "@/lib/agents";
import type { Mission } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 30;

/**
 * POST /api/start — kick off a run.
 *
 * Returns {jobId} for a live run (poll /api/status), or {mock, data} when no
 * backend is configured or the start call fails, so the UI always has something.
 */
export async function POST(req: Request) {
  let mission: Mission;
  let presetId = "general";
  try {
    const body = await req.json();
    mission = {
      title: String(body.title ?? "Untitled mission"),
      goal: String(body.goal ?? ""),
      rounds: Number(body.rounds ?? 3),
    };
    presetId = String(body.presetId ?? "general");
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  const preset = PRESETS.find((p) => p.id === presetId) ?? PRESETS[0];
  const backend = process.env.AIROD_API_URL;

  if (!backend) {
    return NextResponse.json({ mock: true, data: runMock(mission) });
  }

  try {
    const res = await fetch(`${backend.replace(/\/$/, "")}/run/start`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        title: mission.title,
        goal: mission.goal,
        rounds: mission.rounds,
        agents_path: preset.agentsPath,
        oracle: preset.oracle ?? null,
        backtest: preset.backtest ?? {},
        event: preset.event ?? {},
      }),
      signal: AbortSignal.timeout(20_000),
    });
    if (!res.ok) throw new Error(`backend ${res.status}`);
    const j = await res.json();
    return NextResponse.json({ jobId: j.job_id });
  } catch (err) {
    return NextResponse.json({
      mock: true,
      data: runMock(mission),
      warning:
        "Could not start the live run — showing the mock instead. " +
        `(${err instanceof Error ? err.message : "error"})`,
    });
  }
}
