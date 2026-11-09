import { Check } from "lucide-react";

import { ProgressBar, Spinner } from "../ui/Primitives.jsx";

// Mirrors the backend stage plan (app/services/analysis_service.py).
const STAGES = [
  { key: "queued", label: "Queued for processing" },
  { key: "tracking", label: "Load tracking (players, ball, pitch)" },
  { key: "teams", label: "Restore teams & player identities" },
  { key: "metrics", label: "Physical, pose & possession metrics" },
  { key: "gemini", label: "Agentic AI video analysis" },
  { key: "fusion", label: "Fuse events with tracking · ratings" },
  { key: "rendering", label: "Render annotated pose video" },
  { key: "reporting", label: "Graphs, player card & report" },
];
const ORDER = Object.fromEntries(STAGES.map((s, i) => [s.key, i]));

export default function StageTracker({ progress }) {
  const stage = progress?.stage === "selection" ? "teams" : progress?.stage;
  const current = stage === "done" ? STAGES.length : ORDER[stage] ?? 0;
  return (
    <div className="stack" style={{ "--gap": "16px" }}>
      <div className="stack" style={{ "--gap": "8px" }}>
        <div className="spread">
          <span style={{ fontWeight: 600, minWidth: 0 }}>{progress?.message || "Starting..."}</span>
          <span className="mono">{Math.round(progress?.percent ?? 0)}%</span>
        </div>
        <ProgressBar percent={progress?.percent} />
      </div>
      <div className="stages">
        {STAGES.map((stage, i) => {
          const state = i < current ? "done" : i === current ? "active" : "";
          return (
            <div key={stage.key} className={`stage ${state}`}>
              <span className="marker">{state === "done" ? <Check size={13} strokeWidth={3} /> : state === "active" ? <Spinner /> : null}</span>
              {stage.label}
            </div>
          );
        })}
      </div>
    </div>
  );
}
