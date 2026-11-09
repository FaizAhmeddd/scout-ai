import {
  Activity, ArrowLeft, BarChart3, BookOpen, Bot, Crosshair, Database, Download, ExternalLink, Footprints, Gauge,
  LayoutDashboard, Map, RefreshCw, Route, Star, Timer, Trash2, Trophy, UsersRound, Zap,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Methodology from "../components/analysis/Methodology.jsx";
import {
  ATTRIBUTES, Caveats, ChartGrid, EventsTable, FourCorner, KeyMoments, KeyValueTable, RatingsPanel, ScoutingReport, ZoneBars,
} from "../components/analysis/ResultBlocks.jsx";
import StageTracker from "../components/analysis/StageTracker.jsx";
import { Reveal, StaggerGrid, Tilt } from "../components/fx/Motion.jsx";
import TrackingField from "../components/fx/TrackingField.jsx";
import { Topbar } from "../components/layout/AppShell.jsx";
import { EmptyState, Kpi } from "../components/ui/Primitives.jsx";
import { ConnectionBanner, LoadError, Notice, SkeletonPage } from "../components/ui/States.jsx";
import StatusBadge, { isActive } from "../components/ui/StatusBadge.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { analysisApi, videoApi } from "../services/api.js";
import { assetUrl, errorMessage, errorStatus, isNotFound } from "../services/apiClient.js";
import {
  aiStatus, aiStatusNotice, cleanText, count, isNum, jobError, list, num, obj, pct, ratio, relativeTime, share, titleCase, unit,
} from "../utils/format.js";

const PLAYER_CHARTS = {
  physical: ["Speed timeline", "Distance by speed zone", "Work-rate profile"],
  technical: ["Success rates", "Event timeline"],
  tactical: ["Heatmap", "Movement trail", "Event map"],
  ratings: ["Attribute radar"],
};
const TEAM_CHARTS = {
  overview: ["Possession"],
  physical: ["Distance by player", "Top speed by player"],
  technical: ["Team events", "Event timeline"],
  tactical: ["Average positions", "Team heatmap"],
};
const KNOWN_CHARTS = new Set([...Object.values(PLAYER_CHARTS), ...Object.values(TEAM_CHARTS)].flat());

export default function AnalysisDetail() {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const { data: analysis, error, retry } = usePolling(() => analysisApi.get(analysisId), {
    intervalMs: 2000,
    shouldPoll: (a) => isActive(a.status),
    deps: [analysisId],
  });

  if (error && (!analysis || isNotFound(error))) {
    return (
      <>
        <Topbar back="/app/analyses" crumbs={[{ label: "All analyses", to: "/app/analyses" }, { label: "Analysis" }]} />
        <div className="content">
          <LoadError
            error={error}
            onRetry={retry}
            back={{ to: "/app/analyses", label: "All analyses" }}
            notFoundTitle="Analysis not found"
            notFoundText="This analysis may have been deleted (or its video was removed), or the link is incorrect."
          />
        </div>
      </>
    );
  }
  if (!analysis) {
    return (
      <>
        <Topbar back="/app/analyses" crumbs={[{ label: "All analyses", to: "/app/analyses" }, { label: "Loading..." }]} />
        <SkeletonPage />
      </>
    );
  }

  const target = obj(analysis.target);
  const result = obj(analysis.result);
  const metrics = analysis.metrics && typeof analysis.metrics === "object" ? analysis.metrics : null;
  const label = target.label || (target.mode === "player" ? "Player analysis" : "Team analysis");
  const videoLink = `/app/videos/${analysis.video_id}`;

  const act = async (action) => {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      const status = errorStatus(err);
      setActionError(
        status === 409 && /detect|upgraded|tracking/i.test(errorMessage(err))
          ? { text: errorMessage(err), video: true }
          : status === 404
            ? { text: "The video for this analysis no longer exists, so it can't be run again.", video: false }
            : { text: errorMessage(err) }
      );
    } finally {
      setBusy(false);
    }
  };

  const remove = () => {
    if (!window.confirm("Delete this analysis? This cannot be undone.")) return;
    act(async () => {
      await analysisApi.remove(analysisId);
      navigate(videoLink, { replace: true });
    });
  };

  const runAgain = () =>
    act(async () => {
      const defaultLabel =
        target.label === `#${target.jersey_number}` || target.label === `Player ${target.player}` || !target.label;
      const created = await videoApi.startAnalysis(analysis.video_id, {
        team: target.team,
        player: target.mode === "player" ? target.player : null,
        jersey_number: target.mode === "player" ? target.jersey_number ?? null : null,
        player_name: target.mode === "player" && !defaultLabel ? String(target.label).slice(0, 60) : "",
        use_gemini: analysis.use_gemini !== false,
        render_video: analysis.render_video !== false,
      });
      navigate(`/app/analyses/${created.id}`);
    });

  const completed = analysis.status === "completed";

  return (
    <>
      <Topbar
        back={videoLink}
        crumbs={[
          { label: "Video library", to: "/app/library" },
          { label: analysis.video_title || "Video", to: videoLink },
          { label },
        ]}
        actions={
          <>
            {completed && result.report_url && (
              <a className="btn sm hide-sm" href={assetUrl(result.report_url)} target="_blank" rel="noreferrer">
                <ExternalLink size={14} /> Full HTML report
              </a>
            )}
            {completed && result.metrics_url && (
              <a className="btn sm hide-sm" href={assetUrl(result.metrics_url)} target="_blank" rel="noreferrer">
                <Download size={14} /> Data (JSON)
              </a>
            )}
            {!isActive(analysis.status) && (
              <button className="btn ghost danger sm icon-btn" title="Delete analysis" aria-label="Delete analysis" onClick={remove} disabled={busy}>
                <Trash2 size={15} />
              </button>
            )}
          </>
        }
      />
      <div className="content stack" style={{ "--gap": "24px" }}>
        <ConnectionBanner error={error} />
        <Header analysis={analysis} target={target} label={label} metrics={metrics} />
        {actionError && (
          <Notice
            tone="danger"
            title="That didn't work"
            action={actionError.video && <Link className="btn sm" to={videoLink}>Open video</Link>}
          >
            {actionError.text}
          </Notice>
        )}
        {isActive(analysis.status) && <RunningView analysis={analysis} />}
        {analysis.status === "failed" && <FailedView analysis={analysis} onRunAgain={runAgain} busy={busy} videoLink={videoLink} />}
        {completed && !metrics && (
          <Notice tone="warn" title="Detailed metrics are unavailable for this report">
            The analysis finished, but its metrics could not be loaded. You can still open the downloads below, or run the analysis
            again from the video page.
          </Notice>
        )}
        {completed && metrics && (target.mode === "player" ? (
          <PlayerResult analysis={analysis} metrics={metrics} result={result} />
        ) : (
          <TeamResult analysis={analysis} metrics={metrics} result={result} />
        ))}
        {completed && !metrics && <Downloads result={result} />}
        {!["queued", "running", "failed", "completed"].includes(analysis.status) && (
          <Notice tone="warn" title={`Status: ${titleCase(analysis.status || "unknown")}`}>
            This analysis is in an unexpected state. Refresh the page, or run it again from the video page.
          </Notice>
        )}
      </div>
    </>
  );
}

function Header({ analysis, target, label, metrics }) {
  const [thumbFailed, setThumbFailed] = useState(false);
  return (
    <div className="row" style={{ "--gap": "16px", flexWrap: "nowrap", alignItems: "flex-start" }}>
      {target.thumbnail_url && !thumbFailed ? (
        <img src={assetUrl(target.thumbnail_url)} alt="" onError={() => setThumbFailed(true)}
          style={{ width: 60, height: 78, objectFit: "cover", borderRadius: 10, flex: "none" }} />
      ) : (
        <div className="brand-mark" style={{ width: 60, height: 60, background: target.team_color_hex || "var(--panel-2)", flex: "none" }}>
          <UsersRound size={26} color="#000" />
        </div>
      )}
      <div className="stack" style={{ "--gap": "6px", minWidth: 0 }}>
        <div className="row" style={{ "--gap": "8px" }}>
          <StatusBadge status={analysis.status} error={analysis.error} />
          {target.team != null && (
            <span className="badge"><span className="swatch" style={{ background: target.team_color_hex || "var(--line-2)" }} /> Team {target.team}{target.team_color ? ` · ${target.team_color}` : ""}</span>
          )}
          <span className="badge">{target.mode === "player" ? "Single-player analysis" : "Whole-team analysis"}</span>
          {metrics && <span className="badge accent"><Bot size={12} /> AI events: {aiStatus(metrics.gemini_status)}</span>}
          {metrics?.geometry_mode && <span className="badge"><Map size={12} /> {titleCase(metrics.geometry_mode)}</span>}
        </div>
        <h1 className="page-title">{label}</h1>
        <span className="small muted" style={{ overflowWrap: "anywhere" }}>
          {analysis.video_title || "Untitled video"} · started {relativeTime(analysis.created_at) || "recently"}
        </span>
      </div>
    </div>
  );
}

function RunningView({ analysis }) {
  const queued = analysis.status === "queued";
  return (
    <div className="split">
      <Reveal className="card energy">
        {queued ? (
          <div className="stack" style={{ "--gap": "12px" }}>
            <b>Queued</b>
            <p className="small text-2">
              ScoutAI processes one job at a time so each one gets full speed. This analysis starts automatically as soon as
              the jobs ahead of it finish - no need to keep this page open.
            </p>
            <StageTracker progress={analysis.progress} />
          </div>
        ) : (
          <StageTracker progress={analysis.progress} />
        )}
      </Reveal>
      <Reveal className="card stack" delay={0.1}>
        <div className="field-panel" style={{ aspectRatio: "16 / 9" }}>
          <TrackingField density={0.7} />
        </div>
        <h3 className="section-title">While you wait</h3>
        <p className="small text-2">
          Tracking is reused from detection, so most of the time goes to the {analysis.use_gemini !== false ? <><b>AI video analyst</b>, which watches the clip
          and decides which moments to replay and how closely, and to </> : null}<b>rendering</b> the pose-annotated video.
        </p>
        <p className="small text-2">You can leave this page; the job keeps running and the result appears in the library.</p>
      </Reveal>
    </div>
  );
}

function FailedView({ analysis, onRunAgain, busy, videoLink }) {
  const failure = jobError(analysis.error);
  return (
    <div className="card stack" style={{ "--gap": "16px" }}>
      <Notice tone={failure.interrupted ? "warn" : "danger"} title={failure.title}>{failure.message}</Notice>
      <div className="row">
        <button className="btn primary" onClick={onRunAgain} disabled={busy}>
          <RefreshCw size={15} className={busy ? "spin" : ""} /> {busy ? "Starting..." : "Run again with the same settings"}
        </button>
        <Link className="btn" to={videoLink}>
          <ArrowLeft size={15} /> Back to video
        </Link>
      </div>
      <span className="tiny muted">If it keeps failing, try a shorter clip or turn off the annotated video when starting the analysis.</span>
    </div>
  );
}

function AiNotice({ metrics }) {
  if (metrics?.gemini) return null;
  return (
    <Notice icon={Bot} title="Tracking-only report">
      {aiStatusNotice(metrics?.gemini_status)} Distance, speed, sprints, accelerations, cadence and ball possession are fully
      measured from tracking.
    </Notice>
  );
}

function Section({ id, icon: Icon, title, children }) {
  return (
    <section id={id} className="result-section">
      <h2 className="result-section-title"><Icon size={18} /> {title}</h2>
      {children}
    </section>
  );
}

function AnnotatedVideo({ analysis, result }) {
  const [failed, setFailed] = useState(false);
  if (!result.annotated_video_url) {
    return analysis.render_video ? (
      <Notice title="No annotated video for this report">The pose-annotated video could not be produced for this run. All metrics are unaffected.</Notice>
    ) : null;
  }
  if (failed) return <Notice tone="warn" title="The annotated video couldn't be played">Try the download in the Data section, or reload the page.</Notice>;
  return (
    <div className="card flush">
      <video src={assetUrl(result.annotated_video_url)} controls preload="metadata" playsInline onError={() => setFailed(true)}
        style={{ width: "100%", background: "#000" }} />
    </div>
  );
}

function ratingChips(ratings) {
  const estimated = new Set(list(ratings.estimated));
  return (
    <div className="row" style={{ "--gap": "8px" }}>
      {ATTRIBUTES.filter((a) => isNum(ratings[a.key])).map((a) => (
        <span key={a.key} className={`badge rating-chip${estimated.has(a.key) ? " estimated" : ""}`} title={`${a.label}${estimated.has(a.key) ? " (estimate)" : ""}`}>
          <b>{ratings[a.key]}</b> {a.key}{estimated.has(a.key) ? "*" : ""}
        </span>
      ))}
    </div>
  );
}

function PlayerResult({ analysis, metrics, result }) {
  const player = metrics.focus_player && typeof metrics.focus_player === "object" ? metrics.focus_player : null;
  if (!player) {
    return (
      <>
        <Notice tone="warn" title="This player couldn't be measured">
          The selected player wasn't tracked long enough in this clip to build an individual report. Try a player with more
          time on screen, or analyse the whole team.
        </Notice>
        {metrics.team && <TeamResult analysis={analysis} metrics={metrics} result={result} />}
      </>
    );
  }

  const physical = obj(player.physical);
  const pose = obj(player.pose);
  const ball = obj(player.ball);
  const ratings = obj(player.ratings);
  const events = player.events && typeof player.events === "object" ? player.events : null;
  const assessment = player.assessment && typeof player.assessment === "object" ? player.assessment : null;
  const gemini = metrics.gemini && typeof metrics.gemini === "object" ? metrics.gemini : null;
  const playerEvents = list(gemini?.events).filter((e) => e?.is_target);
  const charts = obj(result.chart_urls);
  const shortTrack = isNum(physical.time_tracked_s) && physical.time_tracked_s < 20;


  return (
    <>
      <div className="result-split">
        <div className="result-main stack" style={{ "--gap": "16px" }}>
          <AnnotatedVideo analysis={analysis} result={result} />
          <AiNotice metrics={metrics} />
          {gemini && gemini.target_identified === false && (
            <Notice tone="warn" title="The AI analyst couldn't confidently identify this player">
              {cleanText(gemini.identification_notes) || "Event counts may include actions by a team-mate or miss some actions."}
            </Notice>
          )}
          {shortTrack && (
            <Notice tone="warn" title={`Only ${Math.round(physical.time_tracked_s)} s of measurable tracking`}>
              This player was measurable for a short time, so physical numbers and the PAC/PHY ratings are estimates. Compare
              metres per minute rather than totals.
            </Notice>
          )}
        </div>
        <aside className="result-side stack" style={{ "--gap": "14px" }}>
          {result.player_card_url && <PlayerCard url={result.player_card_url} />}
          <StaggerGrid className="grid" style={{ "--min": "130px" }}>
            <Kpi icon={Trophy} label="Overall" value={isNum(ratings.overall) ? ratings.overall : "-"} unit={ratings.position && ratings.position !== "--" ? ratings.position : undefined} note="ScoutAI rating (0-99)" />
            <Kpi icon={Route} label="Distance" value={num(physical.total_distance_m)} unit={isNum(physical.total_distance_m) ? "m" : undefined} note={`${num(physical.distance_per_min_m)} m/min`} />
            <Kpi icon={Zap} label="Top speed" value={num(physical.top_speed_kmh, 1)} unit={isNum(physical.top_speed_kmh) ? "km/h" : undefined} note="sustained over 1 s" />
            <Kpi icon={Gauge} label="Sprints" value={count(physical.sprints)} note={`${num(physical.high_intensity_distance_m)} m high-intensity`} />
            <Kpi icon={Footprints} label="Ball control" value={num(ball.control_time_s, 1)} unit={isNum(ball.control_time_s) ? "s" : undefined} note={`${count(ball.touches)} possessions`} />
            <Kpi icon={Timer} label="On screen" value={num(player.on_screen_s)} unit={isNum(player.on_screen_s) ? "s" : undefined} note={`${list(player.tracker_fragments).length || 1} tracking segment(s) merged`} />
            {events && <Kpi icon={Crosshair} label="Passes" value={ratio(events.passes_completed, events.passes_attempted)} note={accuracyNote(events)} />}
            {events && <Kpi icon={Activity} label="Dribbles" value={ratio(events.dribbles_successful, events.dribbles_attempted)} note="successful / attempted" />}
          </StaggerGrid>
          {ratingChips(ratings)}
        </aside>
      </div>

      <div className="result-sections">
        <Section id="overview" icon={LayoutDashboard} title="Scouting report">
          <div className="stack" style={{ "--gap": "20px" }}>
            {assessment ? (
              <ScoutingReport assessment={assessment} />
            ) : (
              gemini && (
                <EmptyState icon={Bot} title="No scouting assessment for this player">
                  The AI analyst logged the clip but did not write an individual assessment. Tracking metrics and ratings are unaffected.
                </EmptyState>
              )
            )}
            {list(gemini?.key_moments).length > 0 && (
              <div className="card stack">
                <h3 className="section-title">Key moments</h3>
                <div className="scroll-y"><KeyMoments moments={gemini.key_moments} /></div>
              </div>
            )}
          </div>
        </Section>

        <Section id="physical" icon={Activity} title="Physical">
          <div className="stack" style={{ "--gap": "20px" }}>
            <ChartGrid names={PLAYER_CHARTS.physical} charts={charts} />
            <ZoneBars zones={physical.distance_by_zone_m} />
            <div className="grid fit" style={{ "--min": "340px", alignItems: "start" }}>
              <KeyValueTable title="Physical output (tracking)" rows={[
                ["Total distance", unit(physical.total_distance_m, "m")],
                ["Distance per minute", unit(physical.distance_per_min_m, "m/min"), "Distance ÷ time tracked"],
                ["Average speed", unit(physical.avg_speed_kmh, "km/h", 1), "Including standing and walking"],
                ["Top speed", unit(physical.top_speed_kmh, "km/h", 1), "Best speed held for 1 second"],
                ["High-intensity distance", unit(physical.high_intensity_distance_m, "m"), "Above 20 km/h"],
                ["High-intensity share", pct(physical.high_intensity_distance_m, physical.total_distance_m)],
                ["Sprints", count(physical.sprints), "≥ 25 km/h for ≥ 1 s"],
                ["Accelerations / decelerations", `${count(physical.accelerations)} / ${count(physical.decelerations)}`, "≥ 3 m/s² for ≥ 0.5 s"],
                ["Time tracked", unit(physical.time_tracked_s, "s"), "Measurable time used for physical metrics"],
                ["Time on screen", unit(player.on_screen_s, "s")],
              ]} />
              <KeyValueTable title="Biomechanics (body pose)" rows={[
                ["Running cadence", isNum(pose.cadence_steps_per_min) ? `${num(pose.cadence_steps_per_min)} steps/min` : "Not enough running", "Steps per minute above 9 km/h"],
                ["Trunk lean while running", isNum(pose.trunk_lean_deg) ? `${num(pose.trunk_lean_deg)}°` : "Not enough running", "Torso angle from vertical"],
                ["Keypoint visibility", share(pose.keypoint_visibility), "Share of body points seen clearly"],
              ]} />
              <KeyValueTable title="Ball possession (tracking)" rows={[
                ["Ball control time", unit(ball.control_time_s, "s", 1), "Ball at the player's feet"],
                ["Possessions (touches)", count(ball.touches), "Separate times the player gained the ball"],
                ["Share of screen time on the ball", pct(ball.control_time_s, player.on_screen_s)],
              ]} />
            </div>
            <SprintLog sprints={physical.sprint_details} />
          </div>
        </Section>

        <Section id="technical" icon={Crosshair} title="Technical">
          <div className="stack" style={{ "--gap": "20px" }}>
            {events ? (
              <>
                <ChartGrid names={PLAYER_CHARTS.technical} charts={charts} />
                <EventSummary events={events} />
                {playerEvents.length > 0 ? (
                  <div className="stack" style={{ "--gap": "10px" }}>
                    <h3 className="section-title">Event log ({playerEvents.length})</h3>
                    <EventsTable events={playerEvents} />
                  </div>
                ) : (
                  <EmptyState icon={Crosshair} title="No on-ball actions in this clip">
                    {cleanText(assessment?.summary) || "The AI analyst did not see this player on the ball during the clip."}
                  </EmptyState>
                )}
              </>
            ) : (
              <>
                <AiNotice metrics={metrics} />
                <KeyValueTable title="On the ball (tracking)" rows={[
                  ["Ball control time", unit(ball.control_time_s, "s", 1)],
                  ["Possessions (touches)", count(ball.touches)],
                ]} />
              </>
            )}
          </div>
        </Section>

        <Section id="tactical" icon={Map} title="Tactical">
          <div className="stack" style={{ "--gap": "20px" }}>
            <ChartGrid names={PLAYER_CHARTS.tactical} charts={charts} min="320px" />
            <div className="grid" style={{ "--min": "340px", alignItems: "start" }}>
              {gemini?.tactical_summary && (
                <div className="card stack">
                  <h3 className="section-title">Role & movement</h3>
                  <p className="text-2 small">{cleanText(gemini.tactical_summary)}</p>
                </div>
              )}
              {assessment && (
                <div className="card stack">
                  <h3 className="section-title">Four-corner assessment</h3>
                  <FourCorner corner={assessment.four_corner} />
                </div>
              )}
            </div>
            {!gemini && !Object.keys(charts).some((c) => PLAYER_CHARTS.tactical.includes(c)) && (
              <EmptyState icon={Map} title="No tactical view for this clip">
                Position maps need calibrated pitch positions, and the role summary comes from AI event analysis - neither was
                available for this run.
              </EmptyState>
            )}
          </div>
        </Section>

        <Section id="ratings" icon={Star} title="Ratings">
          <div className="stack" style={{ "--gap": "20px" }}>
            <div className="grid" style={{ "--min": "340px", alignItems: "start" }}>
              <RatingsPanel ratings={ratings} />
              <ChartGrid names={PLAYER_CHARTS.ratings} charts={charts} min="300px" />
            </div>
            {assessment && (
              <div className="card stack">
                <div className="spread">
                  <h3 className="section-title">AI match rating & four-corner model</h3>
                  {isNum(assessment.overall_rating_10) && <span className="badge accent">{Number(assessment.overall_rating_10).toFixed(1)}/10</span>}
                </div>
                <FourCorner corner={assessment.four_corner} />
              </div>
            )}
            <p className="small muted">
              See <a className="link-btn" href="#method">How it's measured</a> for the exact formula behind each rating.
            </p>
          </div>
        </Section>

        <Section id="method" icon={BookOpen} title="How it's measured">
          <div className="stack" style={{ "--gap": "16px" }}>
            <Caveats items={metrics.caveats} />
            <Methodology mode="player" geometryMode={metrics.geometry_mode} estimated={ratings.estimated} aiAvailable={Boolean(gemini)} />
          </div>
        </Section>

        <Section id="data" icon={Database} title="Data & downloads">
          <DataTab metrics={metrics} result={result} />
        </Section>
      </div>
    </>
  );
}

function PlayerCard({ url }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div />;
  return (
    <Reveal className="float" y={40}>
      <Tilt max={12}>
        <img className="card-img" src={assetUrl(url)} alt="Player card" onError={() => setFailed(true)} />
      </Tilt>
    </Reveal>
  );
}

function SprintLog({ sprints }) {
  const rows = list(sprints).filter((s) => s && typeof s === "object");
  if (!rows.length) {
    return <p className="small muted">No sprints (25 km/h or faster for at least 1 s) were recorded while this player was on screen.</p>;
  }
  return (
    <div className="stack" style={{ "--gap": "10px" }}>
      <h3 className="section-title">Sprint log ({rows.length})</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>#</th><th>Start</th><th>End</th><th>Duration</th><th>Peak speed</th><th>Distance</th></tr>
          </thead>
          <tbody>
            {rows.map((s, i) => (
              <tr key={i}>
                <td className="mono">{i + 1}</td>
                <td className="mono">{isNum(s.start_s) ? `${num(s.start_s, 1)} s` : "-"}</td>
                <td className="mono">{isNum(s.end_s) ? `${num(s.end_s, 1)} s` : "-"}</td>
                <td className="num">{isNum(s.start_s) && isNum(s.end_s) ? `${num(s.end_s - s.start_s, 1)} s` : "-"}</td>
                <td className="num">{unit(s.peak_kmh, "km/h", 1)}</td>
                <td className="num">{unit(s.distance_m, "m")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TeamResult({ analysis, metrics, result }) {
  const team = obj(metrics.team);
  const gemini = metrics.gemini && typeof metrics.gemini === "object" ? metrics.gemini : null;
  const players = list(team.players).filter((p) => p && typeof p === "object");
  const events = team.events && typeof team.events === "object" ? team.events : null;
  const charts = obj(result.chart_urls);
  const phys = (p) => obj(p.physical);
  const sum = (pick) => players.reduce((n, p) => n + (isNum(pick(p)) ? Number(pick(p)) : 0), 0);
  const totalDistance = sum((p) => phys(p).total_distance_m);
  const totalHi = sum((p) => phys(p).high_intensity_distance_m);
  const totalSprints = sum((p) => phys(p).sprints);
  const fastest = players
    .filter((p) => isNum(phys(p).top_speed_kmh))
    .sort((a, b) => phys(b).top_speed_kmh - phys(a).top_speed_kmh)[0];
  const zoneTotals = {};
  for (const p of players) {
    for (const [zone, d] of Object.entries(obj(phys(p).distance_by_zone_m))) {
      if (isNum(d)) zoneTotals[zone] = (zoneTotals[zone] ?? 0) + Number(d);
    }
  }
  const teamEvents = list(gemini?.events).filter((e) => e?.is_target);
  const assessments = list(gemini?.assessments).filter((a) => a && typeof a === "object");


  return (
    <>
      <div className="result-split">
        <div className="result-main stack" style={{ "--gap": "16px" }}>
          <AnnotatedVideo analysis={analysis} result={result} />
          <AiNotice metrics={metrics} />
          {gemini && gemini.target_identified === false && (
            <Notice tone="warn" title="The AI analyst couldn't confidently identify this team">
              {cleanText(gemini.identification_notes) || "Event counts may be incomplete."}
            </Notice>
          )}
          {players.length === 0 && (
            <Notice tone="warn" title="No players from this team were measurable">
              No player of this team was on screen for at least 2 seconds with usable tracking, so individual and physical
              numbers are empty. Possession and AI-detected events (if available) are still shown.
            </Notice>
          )}
        </div>
        <aside className="result-side stack" style={{ "--gap": "14px" }}>
          <StaggerGrid className="grid" style={{ "--min": "130px" }}>
        <Kpi icon={BarChart3} label="Possession" value={isNum(team.possession_share) ? `${Math.round(team.possession_share * 100)}%` : "-"} note={team.opponent_color && team.opponent_color !== "unknown" ? `vs ${team.opponent_color}` : "share of ball control"} />
        <Kpi icon={Route} label="Team distance" value={num(totalDistance / 1000, 2)} unit="km" note="while on screen" />
        <Kpi icon={UsersRound} label="Players tracked" value={players.length} note="on screen ≥ 2 s" />
        <Kpi icon={Zap} label="Fastest" value={fastest ? num(phys(fastest).top_speed_kmh, 1) : "-"} unit={fastest ? "km/h" : undefined} note={fastest ? fastest.label || `player ${fastest.player_id}` : "no speed measured"} />
        <Kpi icon={Gauge} label="Sprints" value={count(totalSprints)} note={`${num(totalHi)} m high-intensity`} />
        {events && <Kpi icon={Crosshair} label="Passes" value={ratio(events.passes_completed, events.passes_attempted)} note={accuracyNote(events)} />}
        {events && <Kpi icon={Trophy} label="Shots" value={ratio(events.shots_on_target, events.shots)} note={`on target · ${count(events.goals)} goals`} />}
          </StaggerGrid>
        </aside>
      </div>

      <div className="result-sections">
        <Section id="overview" icon={LayoutDashboard} title="Overview">
          <div className="grid overview-split" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(min(420px, 100%), 1fr))" }}>
            <ChartGrid names={TEAM_CHARTS.overview} charts={charts} min="300px" />
            {list(gemini?.key_moments).length > 0 && (
              <div className="card stack">
                <h3 className="section-title">Key moments</h3>
                <div className="scroll-y"><KeyMoments moments={gemini.key_moments} /></div>
              </div>
            )}
          </div>
        </Section>

        <Section id="physical" icon={Activity} title="Physical">
          <div className="stack" style={{ "--gap": "20px" }}>
            <ChartGrid names={TEAM_CHARTS.physical} charts={charts} />
            {players.length > 0 ? (
              <>
                <ZoneBars zones={zoneTotals} title="Team distance by speed zone" />
                <KeyValueTable title="Team physical output (sum of tracked players)" rows={[
                  ["Total distance", unit(totalDistance, "m")],
                  ["High-intensity distance", unit(totalHi, "m"), "Above 20 km/h"],
                  ["High-intensity share", pct(totalHi, totalDistance)],
                  ["Sprints", count(totalSprints), "≥ 25 km/h for ≥ 1 s"],
                  ["Accelerations / decelerations", `${count(sum((p) => phys(p).accelerations))} / ${count(sum((p) => phys(p).decelerations))}`],
                  ["Fastest player", fastest ? `${fastest.label || `Player ${fastest.player_id}`} · ${num(phys(fastest).top_speed_kmh, 1)} km/h` : "-"],
                ]} />
              </>
            ) : (
              <EmptyState icon={Activity} title="No physical data">No player of this team had enough tracked time to measure.</EmptyState>
            )}
          </div>
        </Section>

        <Section id="technical" icon={Crosshair} title="Technical">
          <div className="stack" style={{ "--gap": "20px" }}>
            {events ? (
              <>
                <ChartGrid names={TEAM_CHARTS.technical} charts={charts} />
                <EventSummary events={events} />
                {teamEvents.length > 0 ? (
                  <div className="stack" style={{ "--gap": "10px" }}>
                    <h3 className="section-title">Event log ({teamEvents.length})</h3>
                    <EventsTable events={teamEvents} />
                  </div>
                ) : (
                  <EmptyState icon={Crosshair} title="No team actions logged">The AI analyst did not log any actions by this team in the clip.</EmptyState>
                )}
              </>
            ) : (
              <AiNotice metrics={metrics} />
            )}
          </div>
        </Section>

        <Section id="tactical" icon={Map} title="Tactical">
          <div className="stack" style={{ "--gap": "20px" }}>
            <ChartGrid names={TEAM_CHARTS.tactical} charts={charts} min="440px" />
            {gemini?.tactical_summary && (
              <div className="card stack">
                <h3 className="section-title">Team shape, pressing & build-up</h3>
                <p className="text-2 small">{cleanText(gemini.tactical_summary)}</p>
              </div>
            )}
            {assessments.length > 0 && (
              <div className="stack" style={{ "--gap": "10px" }}>
                <h3 className="section-title">Individual assessments</h3>
                <div className="grid" style={{ "--min": "320px" }}>
                  {assessments.map((a, i) => (
                    <div key={i} className="card stack" style={{ "--gap": "10px" }}>
                      <div className="spread" style={{ flexWrap: "nowrap" }}>
                        <b className="truncate">{a.player_jersey != null ? `#${a.player_jersey} · ` : ""}{a.approximate_position || "Player"}</b>
                        {isNum(a.overall_rating_10) && <span className="badge accent" style={{ flex: "none" }}>{Number(a.overall_rating_10).toFixed(1)}/10</span>}
                      </div>
                      {a.player_description && <span className="tiny muted">{cleanText(a.player_description)}</span>}
                      {a.summary && <p className="small text-2">{cleanText(a.summary)}</p>}
                      <FourCorner corner={a.four_corner} />
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!gemini && !Object.keys(charts).some((c) => TEAM_CHARTS.tactical.includes(c)) && (
              <EmptyState icon={Map} title="No tactical view for this clip">
                Position maps need calibrated pitch positions, and the shape summary comes from AI event analysis - neither was
                available for this run.
              </EmptyState>
            )}
          </div>
        </Section>

        <Section id="players" icon={UsersRound} title="Players">
          <PlayersTable players={players} />
        </Section>

        <Section id="method" icon={BookOpen} title="How it's measured">
          <div className="stack" style={{ "--gap": "16px" }}>
            <Caveats items={metrics.caveats} />
            <Methodology mode="team" geometryMode={metrics.geometry_mode} aiAvailable={Boolean(gemini)} />
          </div>
        </Section>

        <Section id="data" icon={Database} title="Data & downloads">
          <DataTab metrics={metrics} result={result} />
        </Section>
      </div>
    </>
  );
}

function PlayersTable({ players }) {
  if (!players.length) {
    return <EmptyState icon={UsersRound} title="No players to list">No player of this team was on screen long enough (2 s or more) to measure.</EmptyState>;
  }
  const headers = [
    "Player", "On screen", "Distance", "m/min", "Avg speed", "Top speed", "Sprints", "High-int.", "Acc / Dec",
    "Cadence", "Ball control", "Touches", "PAC", "PHY",
  ];
  return (
    <div className="stack" style={{ "--gap": "10px" }}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {players.map((p, i) => {
              const ph = obj(p.physical);
              const r = obj(p.ratings);
              const est = new Set(list(r.estimated));
              const short = isNum(ph.time_tracked_s) && ph.time_tracked_s < 20;
              return (
                <tr key={p.player_id ?? i}>
                  <td>
                    <b className="truncate" style={{ display: "inline-block", maxWidth: 180 }} title={p.label}>{p.label || `Player ${p.player_id ?? i + 1}`}</b>
                    {short && <span className="badge warn" style={{ marginLeft: 6 }}>short</span>}
                  </td>
                  <td className="num">{unit(p.on_screen_s, "s")}</td>
                  <td className="num">{unit(ph.total_distance_m, "m")}</td>
                  <td className="num">{num(ph.distance_per_min_m)}</td>
                  <td className="num">{unit(ph.avg_speed_kmh, "km/h", 1)}</td>
                  <td className="num">{unit(ph.top_speed_kmh, "km/h", 1)}</td>
                  <td className="num">{count(ph.sprints)}</td>
                  <td className="num">{unit(ph.high_intensity_distance_m, "m")}</td>
                  <td className="num">{count(ph.accelerations)} / {count(ph.decelerations)}</td>
                  <td className="num">{isNum(p.pose?.cadence_steps_per_min) ? num(p.pose.cadence_steps_per_min) : "-"}</td>
                  <td className="num">{unit(p.ball?.control_time_s, "s", 1)}</td>
                  <td className="num">{count(p.ball?.touches)}</td>
                  <td className="num">{isNum(r.PAC) ? `${r.PAC}${est.has("PAC") ? "*" : ""}` : "-"}</td>
                  <td className="num">{isNum(r.PHY) ? `${r.PHY}${est.has("PHY") ? "*" : ""}` : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <span className="tiny muted">
        Sorted by time on screen. "Short" = under 20 s of measurable tracking - treat those numbers as indicative. * = estimate.
        In a whole-team analysis events are counted for the team, so only the tracking-based PAC and PHY ratings are shown per player.
      </span>
    </div>
  );
}

function EventSummary({ events: raw }) {
  const e = obj(raw);
  const duels = (Number(e.aerial_duels) || 0) + (Number(e.ground_duels) || 0) + (Number(e.tackles_attempted) || 0);
  const duelsWon = (Number(e.aerial_duels_won) || 0) + (Number(e.ground_duels_won) || 0) + (Number(e.tackles_won) || 0);
  const defensive = ["tackles_won", "interceptions", "clearances", "blocks", "ball_recoveries"].reduce((n, k) => n + (Number(e[k]) || 0), 0);
  return (
    <div className="grid fit" style={{ "--min": "340px", alignItems: "start" }}>
      <KeyValueTable title="On the ball (AI events)" rows={[
        ["Passes completed", `${ratio(e.passes_completed, e.passes_attempted)} (${pct(e.passes_completed, e.passes_attempted)})`],
        ["Short / long passes", `${count(e.short_passes)} / ${count(e.long_passes)}`],
        ["Long passes completed", ratio(e.long_passes_completed, e.long_passes)],
        ["Progressive passes", count(e.progressive_passes), "Ball moved ~10 m+ towards goal"],
        ["Key passes", count(e.key_passes), "Directly created a shot"],
        ["Assists", count(e.assists)],
        ["Crosses completed", ratio(e.crosses_completed, e.crosses_attempted)],
        ["Dribbles successful", `${ratio(e.dribbles_successful, e.dribbles_attempted)} (${pct(e.dribbles_successful, e.dribbles_attempted)})`],
        ["Shots on target", ratio(e.shots_on_target, e.shots)],
        ["Goals", count(e.goals)],
        ["Possession lost", count(e.possession_lost)],
      ]} />
      <KeyValueTable title="Without the ball (AI events)" rows={[
        ["Tackles won", ratio(e.tackles_won, e.tackles_attempted)],
        ["Interceptions", count(e.interceptions)],
        ["Clearances / blocks", `${count(e.clearances)} / ${count(e.blocks)}`],
        ["Ball recoveries", count(e.ball_recoveries)],
        ["Defensive actions", String(defensive), "Tackles won + interceptions + clearances + blocks + recoveries"],
        ["Duels won (all)", `${duelsWon}/${duels} (${pct(duelsWon, duels)})`, "Aerial + ground duels + tackles"],
        ["Aerial duels won", ratio(e.aerial_duels_won, e.aerial_duels)],
        ["Ground duels won", ratio(e.ground_duels_won, e.ground_duels)],
        ["Fouls committed / won", `${count(e.fouls_committed)} / ${count(e.fouls_won)}`],
        ["Cards (yellow / red)", `${count(e.yellow_cards)} / ${count(e.red_cards)}`],
        ["Saves", count(e.saves)],
      ]} />
    </div>
  );
}

function Downloads({ result }) {
  const links = [
    result.report_url && { href: result.report_url, icon: ExternalLink, label: "Self-contained HTML report", newTab: true },
    result.metrics_url && { href: result.metrics_url, icon: Download, label: "metrics.json", newTab: true },
    result.gemini_events_url && { href: result.gemini_events_url, icon: Bot, label: "events.json", newTab: true },
    result.annotated_video_url && { href: result.annotated_video_url, icon: Download, label: "annotated.mp4", download: true },
    result.player_card_url && { href: result.player_card_url, icon: Download, label: "player card", download: true },
  ].filter(Boolean);
  return (
    <div className="card stack" style={{ "--gap": "12px" }}>
      <b>Downloads</b>
      {links.length ? (
        <div className="row">
          {links.map(({ href, icon: Icon, label, newTab, download }) => (
            <a key={label} className="btn sm" href={assetUrl(href)} {...(newTab ? { target: "_blank", rel: "noreferrer" } : {})} {...(download ? { download: "" } : {})}>
              <Icon size={14} /> {label}
            </a>
          ))}
        </div>
      ) : (
        <span className="small muted">No downloadable files are available for this report.</span>
      )}
    </div>
  );
}

function DataTab({ metrics, result }) {
  const video = obj(metrics.video);
  const charts = obj(result.chart_urls);
  const otherCharts = Object.keys(charts).filter((name) => !KNOWN_CHARTS.has(name));
  return (
    <div className="stack" style={{ "--gap": "16px" }}>
      <Downloads result={result} />
      <KeyValueTable title="About this run" rows={[
        ["Video length", isNum(video.duration_s) ? `${num(video.duration_s, 1)} s` : "-"],
        ["Frame rate", isNum(video.fps) ? `${Math.round(video.fps)} fps` : "-"],
        ["Frames analysed", isNum(video.frames) && isNum(video.frame_stride) ? `${count(Math.ceil(video.frames / Math.max(1, video.frame_stride)))} (every ${video.frame_stride === 1 ? "frame" : `${video.frame_stride} frames`})` : "-"],
        ["Pitch geometry", metrics.geometry_mode ? titleCase(metrics.geometry_mode) : "-"],
        ["AI event analysis", aiStatus(metrics.gemini_status)],
      ]} />
      {otherCharts.length > 0 && (
        <div className="stack" style={{ "--gap": "10px" }}>
          <h3 className="section-title">More charts</h3>
          <ChartGrid names={otherCharts} charts={charts} />
        </div>
      )}
    </div>
  );
}

function accuracyNote(events) {
  return Number(events?.passes_attempted) > 0 ? `${pct(events.passes_completed, events.passes_attempted)} accuracy` : "no passes in this clip";
}
