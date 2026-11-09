import { BarChart3, Clock, Film, Monitor, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { videoApi } from "../../services/api.js";
import { assetUrl, errorMessage } from "../../services/apiClient.js";
import { spotlightHandlers } from "../fx/Motion.jsx";
import { duration, isNum, jobError, relativeTime } from "../../utils/format.js";
import { ProgressBar } from "../ui/Primitives.jsx";
import StatusBadge, { isActive } from "../ui/StatusBadge.jsx";

export default function VideoCard({ video, onDeleted }) {
  const [thumbFailed, setThumbFailed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const title = video.title || video.filename || "Untitled video";
  const failure = video.status === "failed" ? jobError(video.error, "video") : null;

  const remove = async (event) => {
    event.preventDefault(); // the card is a link to the video; the button must not open it
    event.stopPropagation();
    const count = video.analyses_completed ?? 0;
    const also = count ? ` and its ${count} ${count === 1 ? "analysis" : "analyses"}` : "";
    if (!window.confirm(`Delete "${title}"${also}? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await videoApi.remove(video.id);
      onDeleted?.(video.id);
    } catch (err) {
      window.alert(errorMessage(err));
      setDeleting(false);
    }
  };
  return (
    <Link to={`/app/videos/${video.id}`} className="card flush interactive video-card spotlight" {...spotlightHandlers()}>
      <div className="thumb">
        {video.thumbnail_url && !thumbFailed ? (
          <img src={assetUrl(video.thumbnail_url)} alt="" loading="lazy" onError={() => setThumbFailed(true)} />
        ) : (
          <div className="thumb-placeholder"><Film size={28} /></div>
        )}
        <div className="overlay" />
        <div className="tl">
          <StatusBadge status={video.status} error={video.error} />
        </div>
        {!isActive(video.status) && onDeleted && (
          <button type="button" className="tr-delete" title="Delete video" aria-label="Delete video" onClick={remove} disabled={deleting}>
            <Trash2 size={15} />
          </button>
        )}
        <div className="br">{duration(video.duration_s)}</div>
      </div>
      <div className="body stack" style={{ "--gap": "10px" }}>
        <h3 title={title}>{title}</h3>
        {isActive(video.status) ? (
          <div className="stack" style={{ "--gap": "6px" }}>
            <ProgressBar percent={video.progress?.percent} />
            <span className="tiny muted truncate">
              {video.status === "queued" ? "Queued - starts as soon as earlier jobs finish" : video.progress?.message || "Working..."}
            </span>
          </div>
        ) : (
          <div className="row tiny muted" style={{ "--gap": "14px" }}>
            {isNum(video.width) && isNum(video.height) && (
              <span className="row" style={{ "--gap": "5px" }}>
                <Monitor size={13} /> {video.width}×{video.height}
              </span>
            )}
            <span className="row" style={{ "--gap": "5px" }}>
              <BarChart3 size={13} /> {video.analyses_completed ?? 0} {video.analyses_completed === 1 ? "analysis" : "analyses"}
            </span>
            <span className="row" style={{ "--gap": "5px" }}>
              <Clock size={13} /> {relativeTime(video.created_at)}
            </span>
          </div>
        )}
        {failure && (
          <span className="tiny clamp-2" style={{ color: failure.interrupted ? "var(--warn)" : "var(--danger)" }}>{failure.title}</span>
        )}
        {video.status === "ready" && video.detection_outdated && (
          <span className="tiny" style={{ color: "var(--warn)" }}>Tracking upgraded - re-run detection to analyse</span>
        )}
      </div>
    </Link>
  );
}
