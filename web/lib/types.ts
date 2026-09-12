// Shared types for the AIROD dashboard. These mirror airod/models.py.

export type ClaimStatus = "supported" | "contested" | "unsupported";
export type HypothesisStatus =
  | "active"
  | "advanced"
  | "open_question"
  | "rejected";

export interface Evidence {
  source: string;
  quote: string;
  relevance?: string;
}

export interface Claim {
  text: string;
  evidence: Evidence[];
  status: ClaimStatus;
}

export interface Critique {
  authorRole: "critic" | "skeptic";
  text: string;
  leverage: number;
}

export interface Hypothesis {
  statement: string;
  prediction: string;
  claims: Claim[];
  critiques: Critique[];
  confidence: number;
  status: HypothesisStatus;
  roundIndex: number;
}

export interface RoundResult {
  roundIndex: number;
  hypothesis: Hypothesis;
  newSupportedClaims: number;
}

export interface Mission {
  title: string;
  goal: string;
  rounds: number;
}

export interface Agent {
  name: string;
  role: "proposer" | "researcher" | "critic" | "skeptic" | "judge";
  model: string;
  blurb: string;
}

export interface DossierSection {
  title: string;
  markdown: string;
}

export interface RunResponse {
  mode: "mock" | "live";
  mission: Mission;
  agents: Agent[];
  rounds: RoundResult[];
  costUsd: number;
  warning?: string;
  dossier?: DossierSection[];
  synthesizing?: boolean;
}
