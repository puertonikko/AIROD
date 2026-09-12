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

// Presets map a UI choice to a backend team + oracle. The /api/run route
// resolves the preset id and forwards agents_path/oracle/event to the backend.
export interface Preset {
  id: string;
  label: string;
  agentsPath: string;
  oracle?: "backtest" | "event_backtest";
  backtest?: Record<string, unknown>;
  event?: Record<string, unknown>;
  dossier?: boolean;
  title: string;
  goal: string;
}

export const PRESETS: Preset[] = [
  {
    id: "general",
    label: "Open question — general team + web research + R&D dossier",
    agentsPath: "config/agents.general.yaml",
    dossier: true,
    title: "Reach a target horsepower by re-tuning a vehicle via OBD-II feedback",
    goal:
      "Design a safe, methodical way to optimize a gasoline vehicle to a specific " +
      "requested horsepower using OBD-II / piggyback datalog as feedback. Separate " +
      "what OBD-II can READ from what must be WRITTEN (piggyback signal interception " +
      "vs ECU flash), name the parameters that move horsepower and their safe ranges, " +
      "give a closed-loop method to converge on the target, and state the knock/AFR/" +
      "thermal safety limits (off-road/track use).",
  },
  {
    id: "trading",
    label: "Trading strategy — out-of-sample backtest oracle",
    agentsPath: "config/agents.trading.yaml",
    oracle: "backtest",
    backtest: {
      data: { symbols: ["AAA", "BBB", "CCC", "DDD"], days: 900, seed: 7 },
      train_frac: 0.6,
      cost_bps: 5,
      min_oos_sharpe: 0.3,
      max_dd_limit: 0.25,
      min_trades: 5,
    },
    title: "Find a trading edge that survives out-of-sample testing",
    goal:
      "Design a trading strategy whose edge survives an out-of-sample backtest with " +
      "realistic costs. Report expected return, max drawdown, and where the edge breaks.",
  },
  {
    id: "catalyst",
    label: "Catalyst edge — event backtest oracle",
    agentsPath: "config/agents.catalyst.yaml",
    oracle: "event_backtest",
    event: {
      data: "examples/data/catalyst_sample.csv",
      train_frac: 0.6,
      cost_bps: 10,
      min_oos_expectancy_pct: 0,
      max_dd_limit: 0.25,
      min_signals: 10,
    },
    title: "Find a catalyst filter with out-of-sample edge",
    goal:
      "Using the catalyst event log, find a filter (confidence, confirmation, type, " +
      "premarket gap) whose same-day expectancy is positive out-of-sample after costs.",
  },
];
