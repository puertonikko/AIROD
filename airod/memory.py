"""Project memory — the persistent record of everything the team learns.

Backed by SQLite so V1 needs zero setup. The schema is the graph of the
argument: missions have hypotheses, hypotheses have claims and critiques,
claims have evidence, and every model call is logged for cost and audit.

Rejection is first-class: rejected hypotheses stay in the table so the team
can be reminded not to re-explore known dead ends.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .models import (
    Claim,
    ClaimStatus,
    Critique,
    Evidence,
    Hypothesis,
    HypothesisStatus,
    Mission,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    goal TEXT NOT NULL,
    success_criteria TEXT NOT NULL,     -- json list
    budget_usd REAL NOT NULL,
    stall_rounds INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL REFERENCES missions(id),
    statement TEXT NOT NULL,
    prediction TEXT,
    confidence REAL DEFAULT 0,
    status TEXT NOT NULL,
    round_index INTEGER NOT NULL,
    payload TEXT NOT NULL,              -- full json snapshot (claims, critiques)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER REFERENCES missions(id),
    round_index INTEGER,
    agent TEXT,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Memory:
    def __init__(self, path: str = "airod_memory.db") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- missions ---------------------------------------------------------
    def create_mission(self, mission: Mission) -> int:
        cur = self.conn.execute(
            "INSERT INTO missions (title, goal, success_criteria, budget_usd, stall_rounds)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                mission.title,
                mission.goal,
                json.dumps(mission.success_criteria),
                mission.budget_usd,
                mission.stall_rounds,
            ),
        )
        self.conn.commit()
        mission.id = int(cur.lastrowid)
        return mission.id

    def get_mission(self, mission_id: int) -> Mission | None:
        row = self.conn.execute(
            "SELECT * FROM missions WHERE id = ?", (mission_id,)
        ).fetchone()
        if row is None:
            return None
        return Mission(
            id=row["id"],
            title=row["title"],
            goal=row["goal"],
            success_criteria=json.loads(row["success_criteria"]),
            budget_usd=row["budget_usd"],
            stall_rounds=row["stall_rounds"],
        )

    # -- hypotheses -------------------------------------------------------
    def save_hypothesis(self, mission_id: int, h: Hypothesis) -> int:
        payload = json.dumps(h.to_dict())
        if h.id is None:
            cur = self.conn.execute(
                "INSERT INTO hypotheses"
                " (mission_id, statement, prediction, confidence, status, round_index, payload)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    mission_id,
                    h.statement,
                    h.prediction,
                    h.confidence,
                    h.status.value,
                    h.round_index,
                    payload,
                ),
            )
            h.id = int(cur.lastrowid)
        else:
            self.conn.execute(
                "UPDATE hypotheses SET statement=?, prediction=?, confidence=?,"
                " status=?, round_index=?, payload=? WHERE id=?",
                (
                    h.statement,
                    h.prediction,
                    h.confidence,
                    h.status.value,
                    h.round_index,
                    payload,
                    h.id,
                ),
            )
        self.conn.commit()
        return h.id

    def hypotheses_for(
        self, mission_id: int, status: HypothesisStatus | None = None
    ) -> list[Hypothesis]:
        if status is None:
            rows = self.conn.execute(
                "SELECT payload FROM hypotheses WHERE mission_id = ? ORDER BY id",
                (mission_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT payload FROM hypotheses WHERE mission_id = ? AND status = ? ORDER BY id",
                (mission_id, status.value),
            ).fetchall()
        return [self._hydrate(json.loads(r["payload"])) for r in rows]

    # -- cost -------------------------------------------------------------
    def record_call(
        self,
        mission_id: int | None,
        round_index: int,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        self.conn.execute(
            "INSERT INTO model_calls"
            " (mission_id, round_index, agent, model, input_tokens, output_tokens, cost_usd)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mission_id, round_index, agent, model, input_tokens, output_tokens, cost_usd),
        )
        self.conn.commit()

    def total_cost(self, mission_id: int) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM model_calls WHERE mission_id = ?",
            (mission_id,),
        ).fetchone()
        return float(row["total"])

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _hydrate(d: dict[str, Any]) -> Hypothesis:
        claims = [
            Claim(
                text=c["text"],
                evidence=[Evidence(**e) for e in c.get("evidence", [])],
                status=ClaimStatus(c.get("status", "unsupported")),
            )
            for c in d.get("claims", [])
        ]
        critiques = [Critique(**c) for c in d.get("critiques", [])]
        return Hypothesis(
            id=d.get("id"),
            statement=d["statement"],
            prediction=d.get("prediction", ""),
            claims=claims,
            critiques=critiques,
            confidence=d.get("confidence", 0.0),
            status=HypothesisStatus(d.get("status", "active")),
            round_index=d.get("round_index", 0),
            strategy=d.get("strategy", {}),
            backtest=d.get("backtest", {}),
        )
