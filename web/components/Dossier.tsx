"use client";

import { useEffect, useMemo, useRef } from "react";
import { marked } from "marked";
import type { DossierSection } from "@/lib/types";

// Split a section's markdown into text and mermaid segments so we can render
// diagrams with mermaid and prose with marked.
type Segment = { kind: "text"; html: string } | { kind: "mermaid"; code: string };

function toSegments(md: string): Segment[] {
  const out: Segment[] = [];
  const re = /```mermaid\s*([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(md)) !== null) {
    if (m.index > last) {
      out.push({ kind: "text", html: marked.parse(md.slice(last, m.index)) as string });
    }
    out.push({ kind: "mermaid", code: m[1].trim() });
    last = re.lastIndex;
  }
  if (last < md.length) {
    out.push({ kind: "text", html: marked.parse(md.slice(last)) as string });
  }
  return out;
}

export default function Dossier({
  sections,
  title,
}: {
  sections: DossierSection[];
  title: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const rendered = useMemo(
    () => sections.map((s) => ({ title: s.title, segments: toSegments(s.markdown) })),
    [sections],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const mermaid = (await import("mermaid")).default;
      const dark = matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? true;
      mermaid.initialize({ startOnLoad: false, theme: dark ? "dark" : "default" });
      if (!cancelled && ref.current) {
        try {
          await mermaid.run({ nodes: ref.current.querySelectorAll(".mermaid") });
        } catch {
          /* a malformed diagram shouldn't break the page */
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rendered]);

  const download = () => {
    const md = sections.map((s) => `# ${s.title}\n\n${s.markdown}`).join("\n\n---\n\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.replace(/[^a-z0-9]+/gi, "_").slice(0, 60) || "dossier"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="card" ref={ref}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <p className="section-title" style={{ margin: 0 }}>R&amp;D Handoff Dossier</p>
        <button className="btn" onClick={download} style={{ padding: "8px 14px", fontSize: 13 }}>
          ↓ Download .md
        </button>
      </div>
      {rendered.map((sec, i) => (
        <div key={i} className="doc-section">
          <h3>{sec.title}</h3>
          {sec.segments.map((seg, j) =>
            seg.kind === "mermaid" ? (
              <pre className="mermaid" key={j}>
                {seg.code}
              </pre>
            ) : (
              <div key={j} className="doc-md" dangerouslySetInnerHTML={{ __html: seg.html }} />
            ),
          )}
        </div>
      ))}
    </section>
  );
}
