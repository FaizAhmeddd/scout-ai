import { Activity, CheckCircle2, Film, Plus, Search, SearchX, Video, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Reveal, Stagger, StaggerItem } from "../components/fx/Motion.jsx";
import { Topbar } from "../components/layout/AppShell.jsx";
import VideoCard from "../components/library/VideoCard.jsx";
import { EmptyState, Kpi } from "../components/ui/Primitives.jsx";
import { ConnectionBanner, ErrorState, SkeletonCards } from "../components/ui/States.jsx";
import { isActive } from "../components/ui/StatusBadge.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { videoApi } from "../services/api.js";
import { list } from "../utils/format.js";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "ready", label: "Ready" },
  { id: "processing", label: "Processing" },
  { id: "failed", label: "Failed" },
];

export default function Library() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const { data, error, retry } = usePolling(videoApi.list, {
    shouldPoll: (items) => list(items).some((v) => isActive(v.status) || v.analyses_running > 0),
  });
  const videos = data ? list(data) : null;

  const visible = useMemo(() => {
    if (!videos) return [];
    return videos.filter((v) => {
      const matches = String(v.title ?? "").toLowerCase().includes(query.trim().toLowerCase());
      const status =
        filter === "all" ||
        (filter === "processing" ? isActive(v.status) : v.status === filter);
      return matches && status;
    });
  }, [videos, query, filter]);

  const stats = useMemo(() => {
    const list = videos ?? [];
    return {
      videos: list.length,
      analyses: list.reduce((n, v) => n + (Number(v.analyses_completed) || 0), 0),
      processing: list.filter((v) => isActive(v.status)).length + list.reduce((n, v) => n + (Number(v.analyses_running) || 0), 0),
      minutes: list.reduce((n, v) => n + (Number(v.duration_s) || 0), 0) / 60,
    };
  }, [videos]);

  return (
    <>
      <Topbar
        crumbs={[{ label: "Video library" }]}
        actions={
          <Link to="/app/upload" className="btn primary">
            <Plus size={16} /> Upload video
          </Link>
        }
      />
      <div className="content stack" style={{ "--gap": "24px" }}>
        <Reveal>
          <h1 className="page-title">
            {user?.full_name ? <>Welcome back, <span className="accent-gradient">{user.full_name.split(" ")[0]}</span></> : "Welcome back"}
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>Your analysed matches and the ones still processing.</p>
        </Reveal>

        {videos && (
          <Stagger className="grid" style={{ "--min": "200px" }} inView={false}>
            <StaggerItem><Kpi icon={Video} label="Videos" value={stats.videos} note={`${stats.minutes.toFixed(1)} min of footage`} /></StaggerItem>
            <StaggerItem><Kpi icon={CheckCircle2} label="Completed analyses" value={stats.analyses} note="team & player reports" /></StaggerItem>
            <StaggerItem><Kpi icon={Activity} label="Processing now" value={stats.processing} note="detection & analysis jobs" /></StaggerItem>
          </Stagger>
        )}

        <div className="spread">
          <div className="filters">
            {FILTERS.map((f) => (
              <button key={f.id} className={`chip${filter === f.id ? " active" : ""}`} onClick={() => setFilter(f.id)}>
                {f.label}
              </button>
            ))}
          </div>
          <div className="input-icon search-box">
            <Search size={16} />
            <input className="input" placeholder="Search videos" value={query} maxLength={100} aria-label="Search videos"
              onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>

        {videos && <ConnectionBanner error={error} />}
        {!videos && error && <ErrorState error={error} title="Couldn't load your library" onRetry={retry} />}
        {!videos && !error && <SkeletonCards count={6} />}
        {videos && videos.length === 0 && (
          <EmptyState
            icon={Film}
            title="No videos yet"
            action={
              <Link to="/app/upload" className="btn primary">
                <Plus size={16} /> Upload your first match
              </Link>
            }
          >
            Upload a broadcast clip. Players, ball and pitch are detected automatically - then pick a team or a player
            to analyse.
          </EmptyState>
        )}
        {videos && videos.length > 0 && visible.length === 0 && (
          <EmptyState
            icon={SearchX}
            title="No matching videos"
            action={
              <button className="btn" onClick={() => { setQuery(""); setFilter("all"); }}>
                <X size={16} /> Clear search & filter
              </button>
            }
          >
            {query.trim() ? `Nothing in your library matches "${query.trim()}"` : "No videos have this status right now"}
            {filter !== "all" && query.trim() ? ` with the "${FILTERS.find((f) => f.id === filter)?.label}" filter.` : "."}
          </EmptyState>
        )}
        <Stagger className="grid" style={{ "--min": "290px" }} inView={false} animateKey={`${filter}-${query}-${visible.length}`}>
          {visible.map((video) => (
            <StaggerItem key={video.id}>
              <VideoCard video={video} onDeleted={retry} />
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </>
  );
}
