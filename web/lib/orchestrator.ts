// Offline placeholder for the dashboard.
//
// The REAL debate runs on the Python backend (deploy to Railway, set
// AIROD_API_URL). This function only renders the pipeline shape with content
// that is CLEARLY labeled as a mock preview and reflects the actual mission —
// it deliberately fabricates no domain analysis, so a mock run is never mistaken
// for a real answer.

import type { RoundResult, RunResponse } from "./types";
import { DEFAULT_TEAM } from "./agents";

export function runMock(mission: { title: string; goal: string; rounds: number }): RunResponse {
  const title = mission.title?.trim() || "your mission";

  const round: RoundResult = {
    roundIndex: 1,
    newSupportedClaims: 0,
    hypothesis: {
      roundIndex: 1,
      statement: `Mock preview for: “${title}”. This is placeholder output that shows how the loop renders — the team is NOT actually researching or reasoning yet.`,
      prediction:
        "Connect live models (set AIROD_API_URL to your Railway backend, with an ANTHROPIC_API_KEY on Railway) to get a real, web-researched answer to this mission.",
      confidence: 0,
      status: "open_question",
      claims: [
        {
          text: "In mock mode no API key is connected, so no evidence is gathered and no real analysis is produced.",
          status: "unsupported",
          evidence: [],
        },
        {
          text: "Switch the badge to “Live models” to run the real 5-agent team on this exact mission.",
          status: "unsupported",
          evidence: [],
        },
      ],
      critiques: [
        {
          authorRole: "skeptic",
          text: "No backend is reachable from this page, so this is a rendering demo only.",
          leverage: 0,
        },
      ],
    },
  };

  return {
    mode: "mock",
    mission,
    agents: DEFAULT_TEAM,
    rounds: [round],
    costUsd: 0,
  };
}
