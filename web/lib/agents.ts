import type { Agent, Mission } from "./types";

// The default R&D team — mirrors config/agents.yaml.
export const DEFAULT_TEAM: Agent[] = [
  {
    name: "proposer",
    role: "proposer",
    model: "claude-opus-5",
    blurb: "Lead scientist. Proposes one testable hypothesis per round.",
  },
  {
    name: "researcher",
    role: "researcher",
    model: "claude-sonnet-5",
    blurb: "Grounds claims in quoted evidence from its knowledge sector.",
  },
  {
    name: "critic",
    role: "critic",
    model: "claude-opus-5",
    blurb: "Attacks the load-bearing assumptions, blind to authorship.",
  },
  {
    name: "skeptic",
    role: "skeptic",
    model: "claude-sonnet-5",
    blurb: "Enumerates concrete failure modes, shortest-leverage first.",
  },
  {
    name: "judge",
    role: "judge",
    model: "claude-opus-5",
    blurb: "Scores each claim on evidence alone; sets overall confidence.",
  },
];

export const DEFAULT_MISSION: Mission = {
  title: "Solid-state EV battery feasibility",
  goal:
    "Assess whether a solid-state EV battery achieving >500 Wh/kg, 1000-cycle " +
    "life, and <$80/kWh manufacturing cost is plausible with known materials, " +
    "and identify the specific bottlenecks that would have to be solved.",
  rounds: 3,
};

export const ROLE_ORDER: Agent["role"][] = [
  "proposer",
  "researcher",
  "critic",
  "skeptic",
  "judge",
];

export const PROTOCOL_STEPS = [
  { key: "propose", label: "Propose", role: "proposer" },
  { key: "ground", label: "Ground", role: "researcher" },
  { key: "attack", label: "Attack", role: "critic" },
  { key: "score", label: "Score", role: "judge" },
  { key: "resolve", label: "Resolve", role: null },
] as const;
