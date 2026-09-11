"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DEFAULT_TEAM, PRESETS, PROTOCOL_STEPS } from "@/lib/agents";
import type { RunResponse } from "@/lib/types";

export default function Home() {
  const [presetId, setPresetId] = useState(PRESETS[0].id);
  const [title, setTitle] = useState(PRESETS[0].title);
  const [goal, setGoal] = useState(PRESETS[0].goal);
  const [rounds, setRounds] = useState(3);

  const onPreset = (id: string) => {
    const p = PRESETS.find((x) => x.id === id) ?? PRESETS[0];
    setPresetId(p.id);
    setTitle(p.title);
    setGoal(p.goal);
  };
  const [running, setRunning] = useState(false);
  const [resp, setResp] = useState<RunResponse | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };
  useEffect(() => clearTimers, []);

  const run = useCallback(async () => {
    clearTimers();
    setRunning(true);
    setError(null);
    setResp(null);
    setRevealed(0);
    setActiveStep(0);

    // Animate the protocol pipeline while the request is in flight.
    PROTOCOL_STEPS.forEach((_, i) => {
      timers.current.push(setTimeout(() => setActiveStep(i), i * 260));
    });

    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, goal, rounds, presetId }),
      });
      const data = (await res.json()) as RunResponse;
      if (!res.ok) throw new Error((data as any).error || "Run failed");
      setResp(data);
      setActiveStep(-1);
      // Reveal rounds one at a time for a live, unfolding feel.
      data.rounds.forEach((_, i) => {
        timers.current.push(setTimeout(() => setRevealed(i + 1), i * 650));
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setActiveStep(-1);
    } finally {
      setRunning(false);
    }
  }, [title, goal, rounds]);

  const team = resp?.agents ?? DEFAULT_TEAM;
  const mode = resp?.mode ?? "mock";

  return (
    <div className="wrap">
      <header className="masthead">
        <div className="brand">
          <div className="logo">AI</div>
          <div>
            <h1>AIROD</h1>
            <p>An R&amp;D group made of collaborating AI agents.</p>
          </div>
        </div>
        <span className="badge">
          <span className={`dot ${mode}`} />
          {mode === "live" ? "Live models" : "Mock mode"}
        </span>
      </header>

      <div className="stack">
        {/* Mission */}
        <section className="card mission">
          <p className="section-title">Mission</p>
          <label htmlFor="preset">Team &amp; oracle</label>
          <select
            id="preset"
            value={presetId}
            onChange={(e) => onPreset(e.target.value)}
          >
            {PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <label htmlFor="title">Title</label>
          <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <label htmlFor="goal">Goal</label>
          <textarea id="goal" rows={3} value={goal} onChange={(e) => setGoal(e.target.value)} />
          <div className="row">
            <div style={{ width: 120 }}>
              <label htmlFor="rounds">Rounds</label>
              <select
                id="rounds"
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
            <div className="grow" />
            <button className="btn" onClick={run} disabled={running}>
              {running ? <span className="spinner" /> : null}
              {running ? "Running…" : "Assign mission →"}
            </button>
          </div>
        </section>

        {/* Team */}
        <section className="card">
          <p className="section-title">The team</p>
          <div className="grid team">
            {team.map((a) => (
              <div
                key={a.name}
                className={`agent ${
                  running && PROTOCOL_STEPS[activeStep]?.role === a.role ? "active" : ""
                }`}
              >
                <div className="name">{a.name}</div>
                <div className="role">{a.role}</div>
                <div className="blurb">{a.blurb}</div>
                <span className="chip">{a.model}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Protocol pipeline */}
        <section className="card">
          <p className="section-title">Debate protocol</p>
          <div className="pipeline">
            {PROTOCOL_STEPS.map((s, i) => (
              <span key={s.key} style={{ display: "contents" }}>
                <span className={`step ${activeStep === i ? "on" : ""}`}>{s.label}</span>
                {i < PROTOCOL_STEPS.length - 1 && <span className="arrow">→</span>}
              </span>
            ))}
          </div>
        </section>

        {error && <div className="warning">Error: {error}</div>}
        {resp?.warning && <div className="warning">{resp.warning}</div>}

        {/* Results */}
        {resp && (
          <section className="card">
            <p className="section-title">
              Results · {resp.rounds.length} round{resp.rounds.length !== 1 ? "s" : ""} · spent $
              {resp.costUsd.toFixed(4)}
            </p>

            {resp.rounds.slice(0, revealed).map((r) => {
              const h = r.hypothesis;
              return (
                <div className="round" key={r.roundIndex}>
                  <div className="round-head">
                    <span className="round-num">ROUND {r.roundIndex}</span>
                    <span className={`status-pill status-${h.status}`}>
                      {h.status.replace("_", " ")}
                    </span>
                  </div>
                  <div className="hyp">{h.statement}</div>
                  {h.prediction && (
                    <div className="pred">
                      <b>Prediction:</b> {h.prediction}
                    </div>
                  )}

                  <div className="meter">
                    <span style={{ width: `${Math.round(h.confidence * 100)}%` }} />
                  </div>
                  <div className="meter-label">
                    confidence {Math.round(h.confidence * 100)}% · {r.newSupportedClaims} new
                    supported claim{r.newSupportedClaims !== 1 ? "s" : ""}
                  </div>

                  {h.claims.map((c, i) => (
                    <div className={`claim ${c.status}`} key={i}>
                      <div className="claim-top">
                        <span className="claim-status">{c.status}</span>
                        <span className="claim-text">{c.text}</span>
                      </div>
                      {c.evidence.map((ev, j) => (
                        <div className="evidence" key={j}>
                          <span className="src">{ev.source}</span>
                          <q>{ev.quote}</q>
                        </div>
                      ))}
                    </div>
                  ))}

                  {h.critiques.length > 0 && (
                    <div className="objections">
                      {h.critiques.map((cr, i) => (
                        <div className="objection" key={i}>
                          <span className="who">{cr.authorRole}</span>
                          <span>{cr.text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </section>
        )}

        <p className="footer-note">
          {mode === "mock" ? (
            <>
              Running the <b>mock debate engine</b> — instant, offline, no API key. To run real
              models, deploy the Python core to Railway and set{" "}
              <code>AIROD_API_URL</code> in this app&apos;s Vercel environment variables.
            </>
          ) : (
            <>Connected to the live AIROD backend.</>
          )}
        </p>
      </div>
    </div>
  );
}
