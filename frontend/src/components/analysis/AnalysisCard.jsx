import { Trash2, UsersRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { analysisApi } from "../../services/api.js";
import { assetUrl, errorMessage } from "../../services/apiClient.js";
import { spotlightHandlers } from "../fx/Motion.jsx";
import { isNum, jobError, num, obj, relativeTime } from "../../utils/format.js";
import { ProgressBar } from "../ui/Primitives.jsx";
import StatusBadge, { isActive } from "../ui/StatusBadge.jsx";

function Headline({ analysis, mode }) {
  const h = analysis.headline;
  if (!h) return <span className="tiny muted">Open to view the report</span>;
  const items =
    mode === "player"
      ? [
          isNum(h.overall) && ["OVR", h.overall],
          ["Distance", num(h.distance_m, 0, " m")],
          ["Top speed", num(h.top_speed_kmh, 1, " km/h")],
          h.passes && ["Passes", h.passes],
        ]
      : [
          ["Possession", isNum(h.possession) ? `${Math.round(h.possession * 100)}%` : "-"],
          ["Players", isNum(h.players) ? h.players : "-"],
          ["Team distance", num(h.distance_m, 0, " m")],
        ];
  return (
    <div className="row tiny" style={{ "--gap": "14px" }}>
      {items.filter(Boolean).map(([label, value]) => (
        <span key={label}>
          <span className="muted">{label} </span>
          <b>{value}</b>
        </span>
      ))}
    </div>
  );
}

export default function AnalysisCard({ analysis, showVideo = false, onDeleted }) {
  const [deleting, setDeleting] = useState(false);
  const target = obj(analysis?.target);
  const mode = target.mode === "player" ? "player" : "team";
  const label = target.label || (mode === "player" ? "Player analysis" : "Team analysis");
  const failure = analysis.status === "failed" ? jobError(analysis.error) : null;

  const remove = async (event) => {
    event.preventDefault(); // the card is a link to the report; the button must not open it
    event.stopPropagation();
    if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await analysisApi.remove(analysis.id);
      onDeleted?.(analysis.id);
    } catch (err) {
      window.alert(errorMessage(err));
      setDeleting(false);
    }
  };
  return (
    <Link to={`/app/analyses/${analysis.id}`} className={`card interactive analysis-card row spotlight${isActive(analysis.status) ? " energy" : ""}`} {...spotlightHandlers()} style={{ "--gap": "14px", flexWrap: "nowrap" }}>
      {target.thumbnail_url ? (
        <img className="target-thumb" src={assetUrl(target.thumbnail_url)} alt="" onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} />
      ) : (
        <div className="target-thumb" style={{ display: "grid", placeItems: "center", background: target.team_color_hex || "var(--panel-2)" }}>
          <UsersRound size={22} color="#000" />
        </div>
      )}
      <div className="stack" style={{ "--gap": "6px", minWidth: 0, flex: 1 }}>
        <div className="spread" style={{ flexWrap: "nowrap", minWidth: 0 }}>
          <div className="row" style={{ "--gap": "8px", minWidth: 0, flexWrap: "nowrap" }}>
            <span className="swatch" style={{ background: target.team_color_hex || "var(--line-2)" }} />
            <b className="truncate" title={label}>{label}</b>
            <span className="badge" style={{ flex: "none" }}>{mode === "player" ? "Player" : "Team"}</span>
          </div>
          <StatusBadge status={analysis.status} error={analysis.error} />
        </div>
        {showVideo && <span className="tiny muted truncate" title={analysis.video_title}>{analysis.video_title || "Untitled video"}</span>}
        {isActive(analysis.status) ? (
          <div className="stack" style={{ "--gap": "4px" }}>
            <ProgressBar percent={analysis.progress?.percent} />
            <span className="tiny muted truncate">
              {analysis.status === "queued" ? "Queued - starts as soon as earlier jobs finish" : analysis.progress?.message || "Working..."}
            </span>
          </div>
        ) : failure ? (
          <span className="tiny clamp-2" style={{ color: failure.interrupted ? "var(--warn)" : "var(--danger)" }}>{failure.title}</span>
        ) : (
          <Headline analysis={analysis} mode={mode} />
        )}
        <div className="spread" style={{ flexWrap: "nowrap" }}>
          <span className="tiny muted">{relativeTime(analysis.created_at)}</span>
          {!isActive(analysis.status) && onDeleted && (
            <button type="button" className="btn ghost danger sm icon-btn" title="Delete analysis" aria-label="Delete analysis" onClick={remove} disabled={deleting}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
    </Link>
  );
}
