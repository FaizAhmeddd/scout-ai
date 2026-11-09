import { Clock, Film, HardDrive, Monitor, RefreshCw, ScanSearch, Trash2, UsersRound } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import AnalysisCard from "../components/analysis/AnalysisCard.jsx";
import { Reveal, ScanFrame, Stagger, StaggerItem } from "../components/fx/Motion.jsx";
import { Topbar } from "../components/layout/AppShell.jsx";
import { EmptyState, ProgressBar } from "../components/ui/Primitives.jsx";
import { ConnectionBanner, ErrorState, LoadError, Notice, SkeletonPage, SkeletonRows } from "../components/ui/States.jsx";
import StatusBadge, { isActive } from "../components/ui/StatusBadge.jsx";
import TargetPicker from "../components/video/TargetPicker.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { videoApi } from "../services/api.js";
import { assetUrl, errorMessage, errorStatus, isNotFound } from "../services/apiClient.js";
import { duration, isNum, jobError, list, relativeTime } from "../utils/format.js";

export default function VideoDetail() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [thumbFailed, setThumbFailed] = useState(false);

  const { data: video, error, retry: retryVideo, setData } = usePolling(() => videoApi.get(videoId), {
    shouldPoll: (v) => isActive(v.status),
    deps: [videoId],
  });
  const { data: analysesData, error: analysesError, retry: retryAnalyses } = usePolling(() => videoApi.analyses(videoId), {
    shouldPoll: (items) => list(items).some((a) => isActive(a.status)),
    deps: [videoId],
  });
  const analyses = analysesData ? list(analysesData) : null;

  const act = async (action) => {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(errorMessage(err));
      // A 409 usually means the video changed state server-side (e.g. tracking upgraded) - reload to show why.
      if (errorStatus(err) === 409) retryVideo();
      if (errorStatus(err) === 404) retryVideo();
    } finally {
      setBusy(false);
    }
  };

  const startAnalysis = (payload) =>
    act(async () => {
      const analysis = await videoApi.startAnalysis(videoId, payload);
      navigate(`/app/analyses/${analysis.id}`);
    });

  const retryDetection = () =>
    act(async () => {
      setData(await videoApi.retryDetection(videoId));
      retryVideo();
    });

  const remove = () => {
    if (!window.confirm(`Delete "${video?.title || "this video"}" and all its analyses? This cannot be undone.`)) return;
    act(async () => {
      await videoApi.remove(videoId);
      navigate("/app/library", { replace: true });
    });
  };

  const back = { to: "/app/library", label: "Back to library" };

  if (error && (!video || isNotFound(error))) {
    return (
      <>
        <Topbar back="/app/library" crumbs={[{ label: "Video library", to: "/app/library" }, { label: "Video" }]} />
        <div className="content">
          <LoadError
            error={error}
            onRetry={retryVideo}
            back={back}
            notFoundTitle="Video not found"
            notFoundText="This video may have been deleted, or the link is incorrect."
          />
        </div>
      </>
    );
  }
  if (!video) {
    return (
      <>
        <Topbar back="/app/library" crumbs={[{ label: "Video library", to: "/app/library" }, { label: "Loading..." }]} />
        <SkeletonPage kpis={0} />
      </>
    );
  }

  const teams = list(video.teams);
  const title = video.title || video.filename || "Untitled video";
  const processing = isActive(video.status);
  const running = list(analyses).some((a) => isActive(a.status));
  const failure = video.status === "failed" ? jobError(video.error, "video") : null;
  const noPlayers = video.status === "ready" && !video.detection_outdated && teams.length === 0;

  return (
    <>
      <Topbar
        back="/app/library"
        crumbs={[{ label: "Video library", to: "/app/library" }, { label: title }]}
        actions={
          <button
            className="btn ghost danger sm"
            onClick={remove}
            disabled={busy || processing || running}
            title={processing || running ? "Wait until processing finishes to delete this video" : "Delete video"}
          >
            <Trash2 size={15} /> Delete
          </button>
        }
      />
      <div className="content stack" style={{ "--gap": "24px" }}>
        <ConnectionBanner error={error} />
        <Reveal className={`card flush video-hero${processing ? " energy" : ""}`}>
          {video.thumbnail_url && !thumbFailed ? (
            <ScanFrame label={processing ? "DETECTING PLAYERS" : "MATCH VIDEO"} className="flat">
              <img src={assetUrl(video.thumbnail_url)} alt="" style={{ height: "100%", width: "100%", objectFit: "cover" }} onError={() => setThumbFailed(true)} />
            </ScanFrame>
          ) : (
            <div className="thumb-placeholder"><Film size={32} /></div>
          )}
          <div className="stack" style={{ padding: 24, "--gap": "14px", minWidth: 0 }}>
            <div className="row">
              <StatusBadge status={video.status} error={video.error} />
              <span className="tiny muted">Uploaded {relativeTime(video.created_at)}</span>
            </div>
            <h1 className="page-title">{title}</h1>
            <div className="row small text-2" style={{ "--gap": "18px" }}>
              <span className="row" style={{ "--gap": "6px" }}><Clock size={15} /> {duration(video.duration_s)}</span>
              {isNum(video.width) && isNum(video.height) && (
                <span className="row" style={{ "--gap": "6px" }}><Monitor size={15} /> {video.width}×{video.height}{isNum(video.fps) ? ` @ ${Math.round(video.fps)} fps` : ""}</span>
              )}
              {isNum(video.size_mb) && <span className="row" style={{ "--gap": "6px" }}><HardDrive size={15} /> {video.size_mb} MB</span>}
            </div>
            {processing && (
              <div className="stack" style={{ "--gap": "8px", maxWidth: 560 }}>
                <div className="spread small">
                  <span>{video.status === "queued" ? "Queued - starts as soon as earlier jobs finish" : video.progress?.message || "Detecting players..."}</span>
                  <span className="mono">{Math.round(Number(video.progress?.percent) || 0)}%</span>
                </div>
                <ProgressBar percent={video.progress?.percent} indeterminate={video.status === "queued"} />
                <span className="tiny muted">You can leave this page - detection keeps running in the background.</span>
              </div>
            )}
            {failure && (
              <div className="stack" style={{ "--gap": "10px" }}>
                <Notice tone={failure.interrupted ? "warn" : "danger"} title={failure.title}>{failure.message}</Notice>
                <button className="btn primary" style={{ alignSelf: "flex-start" }} onClick={retryDetection} disabled={busy}>
                  <RefreshCw size={15} className={busy ? "spin" : ""} /> {busy ? "Restarting..." : "Retry detection"}
                </button>
              </div>
            )}
          </div>
        </Reveal>

        {actionError && <Notice tone="danger" title="That didn't work">{actionError}</Notice>}

        {video.status === "ready" && video.detection_outdated && (
          <Notice
            tone="warn"
            title="Player tracking has been upgraded"
            action={
              <button className="btn primary" onClick={retryDetection} disabled={busy}>
                <RefreshCw size={15} className={busy ? "spin" : ""} /> Re-run detection
              </button>
            }
          >
            ScoutAI's tracking improved since this video was processed. Re-run detection so the player list matches the improved
            tracking before starting a new analysis. Existing reports are kept.
          </Notice>
        )}

        {noPlayers && (
          <EmptyState
            icon={UsersRound}
            title="No teams or players were detected"
            action={
              <button className="btn primary" onClick={retryDetection} disabled={busy}>
                <RefreshCw size={15} /> Re-run detection
              </button>
            }
          >
            ScoutAI couldn't find enough players on the pitch in this clip. It works best with wide broadcast or tactical
            camera footage - close-ups, replays and crowd shots don't contain trackable players.
          </EmptyState>
        )}

        {video.status === "ready" && !video.detection_outdated && teams.length > 0 && (
          <section className="card">
            <div className="spread" style={{ marginBottom: 20 }}>
              <div>
                <h2 className="section-title">New analysis</h2>
                <p className="small muted">Teams and players were detected automatically. Choose what to analyse.</p>
              </div>
            </div>
            <TargetPicker teams={teams} onRun={startAnalysis} busy={busy} />
          </section>
        )}

        <section className="stack" style={{ "--gap": "12px" }}>
          <h2 className="section-title">Analyses of this video</h2>
          {!analyses && analysesError ? (
            <ErrorState error={analysesError} title="Couldn't load the analyses" onRetry={retryAnalyses} compact />
          ) : !analyses ? (
            <SkeletonRows count={2} />
          ) : analyses.length ? (
            <Stagger className="grid" style={{ "--min": "360px" }} inView={false} animateKey={analyses.length}>
              {analyses.map((a) => (
                <StaggerItem key={a.id}>
                  <AnalysisCard analysis={a} onDeleted={retryAnalyses} />
                </StaggerItem>
              ))}
            </Stagger>
          ) : (
            <EmptyState icon={ScanSearch} title="No analyses yet">
              {video.status === "ready"
                ? "Pick a team or a player above to run the first analysis."
                : video.status === "failed"
                  ? "Once detection succeeds you can pick a team or a player to analyse."
                  : "As soon as detection finishes you can pick a team or a player to analyse."}
            </EmptyState>
          )}
        </section>
      </div>
    </>
  );
}
