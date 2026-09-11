// Mock debate engine for the dashboard.
//
// This is the "demo brain" — a faithful, deterministic stand-in for the Python
// orchestrator (airod/orchestrator.py) running in --mock mode. It runs instantly
// with no API key and no cost, so the UI works the moment it's deployed.
//
// For real-model runs the API route proxies to the Python backend instead
// (see app/api/run/route.ts). The content below is illustrative, not research.

import type { Hypothesis, Mission, RoundResult, RunResponse } from "./types";
import { DEFAULT_TEAM } from "./agents";

const SCRIPT: Hypothesis[] = [
  {
    roundIndex: 1,
    statement:
      "A sulfide-based solid electrolyte with a thin protective interlayer is the " +
      "most promising path to the target energy density.",
    prediction: "At 25°C, interface resistance stays below 30 Ω·cm² over 1000 cycles.",
    confidence: 0.45,
    status: "advanced",
    critiques: [
      {
        authorRole: "critic",
        text: "The dendrite-suppression claim has no cited evidence and is the load-bearing assumption for cycle life.",
        leverage: 9,
      },
      {
        authorRole: "critic",
        text: "Interface resistance below 30 Ω·cm² at 25°C is optimistic versus reported values.",
        leverage: 6,
      },
      {
        authorRole: "skeptic",
        text: "Dendrites still nucleate at grain boundaries above 4C charging.",
        leverage: 0,
      },
      {
        authorRole: "skeptic",
        text: "Sulfide electrolytes react with moisture, complicating dry-room manufacturing.",
        leverage: 0,
      },
    ],
    claims: [
      {
        text: "Sulfide electrolytes reach ionic conductivity comparable to liquid electrolytes.",
        status: "supported",
        evidence: [
          {
            source: "solid_electrolytes.md",
            quote:
              "Argyrodite sulfide electrolytes exhibit room-temperature ionic conductivities on the order of 1-10 mS/cm, comparable to liquid electrolytes.",
            relevance: "Directly supports the conductivity claim.",
          },
        ],
      },
      {
        text: "A protective interlayer suppresses lithium dendrite formation at high rates.",
        status: "unsupported",
        evidence: [],
      },
    ],
  },
  {
    roundIndex: 2,
    statement:
      "Pairing the sulfide electrolyte with an engineered interlayer raises critical " +
      "current density, with garnet oxides as a stability fallback.",
    prediction: "Critical current density exceeds 1 mA/cm² at 25°C without dendrite breakthrough.",
    confidence: 0.52,
    status: "advanced",
    critiques: [
      {
        authorRole: "critic",
        text: "Durability of the interlayer over 1000 cycles under fast charging is unproven at scale.",
        leverage: 8,
      },
      {
        authorRole: "skeptic",
        text: "Garnet oxides need >1000°C sintering, which does not map onto existing gigafactory tooling.",
        leverage: 0,
      },
    ],
    claims: [
      {
        text: "Interface coatings raise the critical current density of solid-state cells.",
        status: "contested",
        evidence: [
          {
            source: "solid_electrolytes.md",
            quote:
              "Thin protective interlayers and interface coatings have been shown to raise critical current density, but long-term durability over 1000 cycles under fast charging remains unproven at scale.",
            relevance: "Supports the mechanism but flags the durability gap.",
          },
        ],
      },
      {
        text: "Garnet oxides are a chemically stable fallback electrolyte against lithium metal.",
        status: "supported",
        evidence: [
          {
            source: "solid_electrolytes.md",
            quote:
              "Garnet oxides such as LLZO (Li7La3Zr2O12) are chemically stable against lithium metal and non-flammable.",
            relevance: "Supports the fallback-stability claim.",
          },
        ],
      },
    ],
  },
  {
    roundIndex: 3,
    statement:
      "Manufacturing yield at scale — not chemistry — is the dominant bottleneck to " +
      "the <$80/kWh cost target.",
    prediction: "Cell cost stays above $80/kWh until defect rates fall to gigafactory levels.",
    confidence: 0.5,
    status: "open_question",
    critiques: [
      {
        authorRole: "critic",
        text: "The cost conclusion rests on yield figures that no public model pins down.",
        leverage: 7,
      },
      {
        authorRole: "skeptic",
        text: "A process that works in the lab can be uneconomical if defect rates stay high.",
        leverage: 0,
      },
    ],
    claims: [
      {
        text: "Yield at scale is the dominant unknown in published cost models.",
        status: "contested",
        evidence: [
          {
            source: "economics.md",
            quote:
              "Yield at scale is the dominant unknown in every published cost model; a process that works in the lab can be uneconomical if defect rates stay high.",
            relevance: "Supports the claim but is itself an admission of uncertainty.",
          },
        ],
      },
      {
        text: "Sulfide cells can reuse roll-to-roll processing, easing scale-up.",
        status: "contested",
        evidence: [
          {
            source: "economics.md",
            quote:
              "Sulfide-based cells may reuse roll-to-roll processing similar to conventional lithium-ion, which is favorable for scale-up.",
            relevance: "Hedged with 'may'; not a firm result.",
          },
        ],
      },
    ],
  },
];

function countSupported(h: Hypothesis): number {
  return h.claims.filter((c) => c.status === "supported").length;
}

export function runMock(mission: Mission): RunResponse {
  const maxRounds = Math.max(1, Math.min(mission.rounds || 3, 6));
  const rounds: RoundResult[] = [];
  let stall = 0;

  for (let i = 0; i < maxRounds; i++) {
    const hyp = SCRIPT[Math.min(i, SCRIPT.length - 1)];
    const newSupported = countSupported(hyp);
    rounds.push({
      roundIndex: i + 1,
      hypothesis: { ...hyp, roundIndex: i + 1 },
      newSupportedClaims: newSupported,
    });
    if (newSupported === 0) {
      stall += 1;
      if (stall >= 2) break;
    } else {
      stall = 0;
    }
  }

  return {
    mode: "mock",
    mission,
    agents: DEFAULT_TEAM,
    rounds,
    costUsd: 0,
  };
}
