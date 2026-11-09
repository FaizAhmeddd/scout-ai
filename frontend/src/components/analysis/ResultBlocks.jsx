import { CheckCircle2, CircleDot, MinusCircle, Quote, XCircle } from "lucide-react";
import { useState } from "react";

import { assetUrl } from "../../services/apiClient.js";
import { cleanText, duration, isNum, list, num, obj, titleCase } from "../../utils/format.js";
import { spotlightHandlers, StaggerGrid } from "../fx/Motion.jsx";
import { ProgressBar } from "../ui/Primitives.jsx";

// Mirrors backend kinematics.speed_zones_kmh (config/config.yaml) - FIFA EPTS-style intensity bands.
export const SPEED_ZONES = [
  { key: "walking", label: "Walking", band: "0-7 km/h", color: "#64748b" },
  { key: "jogging", label: "Jogging", band: "7-15 km/h", color: "#38bdf8" },
  { key: "running", label: "Running", band: "15-20 km/h", color: "#22c55e" },
  { key: "high_speed", label: "High-speed running", band: "20-25 km/h", color: "#f59e0b" },
  { key: "sprinting", label: "Sprinting", band: "25+ km/h", color: "#f85149" },
];

export const ATTRIBUTES = [
  { key: "PAC", label: "Pace", source: "tracking" },
  { key: "SHO", label: "Shooting", source: "events" },
  { key: "PAS", label: "Passing", source: "events" },
  { key: "DRI", label: "Dribbling", source: "events" },
  { key: "DEF", label: "Defending", source: "events" },
  { key: "PHY", label: "Physical", source: "tracking" },
];

// Event types where "successful" has no meaning (the action itself is the stat).
const NEUTRAL_OUTCOME = new Set([
  "interception", "clearance", "block", "ball_recovery", "possession_lost", "foul_committed", "foul_won", "card",
]);

function ChartFigure({ name, url }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    <figure className="card chart-card spotlight" style={{ margin: 0, height: "100%" }} {...spotlightHandlers()}>
      <figcaption>{name}</figcaption>
      <a href={assetUrl(url)} target="_blank" rel="noreferrer">
        <img src={assetUrl(url)} alt={name} loading="lazy" onError={() => setFailed(true)} />
      </a>
    </figure>
  );
}

export function ChartGrid({ names, charts, min = "440px" }) {
  const available = list(names).filter((n) => typeof charts?.[n] === "string" && charts[n]);
  if (!available.length) return null;
  return (
    <StaggerGrid className="grid" style={{ "--min": min }} animateKey={available.join()}>
      {available.map((name) => (
        <ChartFigure key={name} name={name} url={charts[name]} />
      ))}
    </StaggerGrid>
  );
}

/** rows: [label, value, hint?]. Missing values render as "-". */
export function KeyValueTable({ title, rows }) {
  const items = list(rows).filter(Boolean);
  if (!items.length) return null;
  return (
    <div className="table-wrap scroll-table">
      <table>
        <thead>
          <tr>
            <th colSpan={2}>{title}</th>
          </tr>
        </thead>
        <tbody>
          {items.map(([key, value, hint], i) => (
            <tr key={`${i}-${key}`}>
              <td className="text-2" style={{ whiteSpace: "normal" }}>
                {key}
                {hint && <div className="tiny muted" style={{ marginTop: 2 }}>{hint}</div>}
              </td>
              <td className="num" style={{ textAlign: "right", fontWeight: 600 }}>
                {value === null || value === undefined || value === "" || Number.isNaN(value) ? "-" : value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FourCorner({ corner }) {
  const c = obj(corner);
  const keys = ["technical", "tactical", "physical", "mental"].filter((k) => isNum(c[k]));
  if (!keys.length) return <span className="small muted">Not assessed for this clip.</span>;
  return (
    <div className="stack corner-bars" style={{ "--gap": "10px" }}>
      {keys.map((k) => (
        <div key={k} className="bar">
          <span className="text-2">{titleCase(k)}</span>
          <ProgressBar percent={Number(c[k]) * 10} />
          <b className="mono">{Number(c[k]).toFixed(1)}</b>
        </div>
      ))}
    </div>
  );
}

function BulletList({ items, empty }) {
  const values = list(items).filter((s) => typeof s === "string" && s.trim());
  if (!values.length) return <span className="small muted">{empty}</span>;
  return (
    <ul className="pill-list small text-2" style={{ margin: 0, paddingLeft: 18 }}>
      {values.map((s, i) => <li key={i}>{cleanText(s)}</li>)}
    </ul>
  );
}

export function ScoutingReport({ assessment }) {
  if (!assessment || typeof assessment !== "object") return null;
  const rating = isNum(assessment.overall_rating_10) ? ` · match rating ${Number(assessment.overall_rating_10).toFixed(1)}/10` : "";
  return (
    <div className="card stack" style={{ "--gap": "18px" }}>
      <div>
        <div className="eyebrow">AI scouting report</div>
        <h3 className="section-title" style={{ marginTop: 4 }}>
          {assessment.approximate_position || "Position not assessed"}{rating}
        </h3>
      </div>
      {assessment.summary && (
        <p className="quote">
          <Quote size={14} style={{ display: "inline", marginRight: 6, color: "var(--accent)" }} />
          {cleanText(assessment.summary)}
        </p>
      )}
      <div className="grid" style={{ "--min": "260px" }}>
        <div>
          <div className="small" style={{ fontWeight: 700, color: "var(--pitch)", marginBottom: 6 }}>Strengths</div>
          <BulletList items={assessment.strengths} empty="No specific strengths noted in this clip." />
        </div>
        <div>
          <div className="small" style={{ fontWeight: 700, color: "var(--warn)", marginBottom: 6 }}>Areas to improve</div>
          <BulletList items={assessment.areas_to_improve} empty="No specific improvements noted in this clip." />
        </div>
        <div>
          <div className="small" style={{ fontWeight: 700, marginBottom: 10 }}>Four-corner model</div>
          <FourCorner corner={assessment.four_corner} />
        </div>
      </div>
    </div>
  );
}

function Outcome({ event }) {
  if (NEUTRAL_OUTCOME.has(event.event_type)) {
    return <span className="row small muted" style={{ "--gap": "4px", flexWrap: "nowrap" }}><MinusCircle size={14} /> Recorded</span>;
  }
  return event.successful ? (
    <span className="row small" style={{ "--gap": "4px", color: "var(--pitch)", flexWrap: "nowrap" }}><CheckCircle2 size={14} /> Success</span>
  ) : (
    <span className="row small" style={{ "--gap": "4px", color: "var(--danger)", flexWrap: "nowrap" }}><XCircle size={14} /> Unsuccessful</span>
  );
}

function eventTags(e) {
  const tags = [];
  if (e.event_type === "pass" && e.pass_length && e.pass_length !== "not_a_pass") tags.push(`${e.pass_length} pass`);
  if (e.progressive) tags.push("progressive");
  if (e.key_pass) tags.push("key pass");
  if (e.assist) tags.push("assist");
  if (e.goal) tags.push("goal");
  if (e.event_type === "card" && e.card_color) tags.push(`${e.card_color} card`);
  return tags;
}

const CONFIDENCE_TONE = { high: "ok", medium: "", low: "warn" };

export function EventsTable({ events }) {
  const rows = list(events)
    .filter((e) => e && typeof e === "object")
    .sort((a, b) => (Number(a.timestamp_s) || 0) - (Number(b.timestamp_s) || 0));
  if (!rows.length) return null;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Event</th>
            <th>Outcome</th>
            <th>Player</th>
            <th>Confidence</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e, i) => (
            <tr key={i}>
              <td className="mono">{duration(e.timestamp_s)}</td>
              <td>
                <div className="row" style={{ "--gap": "4px" }}>
                  <span className="badge">{titleCase(e.event_type || "event")}</span>
                  {eventTags(e).map((t) => <span key={t} className="badge accent">{t}</span>)}
                </div>
              </td>
              <td><Outcome event={e} /></td>
              <td className="small">{e.player_jersey != null ? `#${e.player_jersey}` : e.team_kit_color || "-"}</td>
              <td className="small">
                {e.confidence ? <span className={`badge ${CONFIDENCE_TONE[e.confidence] ?? ""}`}>{e.confidence}</span> : "-"}
              </td>
              <td className="wrap small text-2">{cleanText(e.description) || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function KeyMoments({ moments }) {
  const items = list(moments).filter((m) => m && typeof m === "object");
  if (!items.length) return null;
  return (
    <div className="stack" style={{ "--gap": "10px" }}>
      {items.map((m, i) => (
        <div key={i} className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap", "--gap": "14px" }}>
          <span className="badge accent mono" style={{ flex: "none" }}>{duration(m.timestamp_s)}</span>
          <div style={{ minWidth: 0, overflowWrap: "anywhere" }}>
            <div style={{ fontWeight: 700 }}>{cleanText(m.title) || "Moment"}</div>
            {m.description && <div className="small text-2">{cleanText(m.description)}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Caveats({ items }) {
  const values = list(items).filter((c) => typeof c === "string" && c.trim());
  if (!values.length) return null;
  return (
    <div className="card stack" style={{ "--gap": "10px" }}>
      <div className="row" style={{ "--gap": "8px" }}>
        <CircleDot size={16} color="var(--warn)" />
        <b>Caveats for this report</b>
      </div>
      <ul className="small text-2" style={{ margin: 0, paddingLeft: 18 }}>
        {values.map((c, i) => <li key={i} style={{ margin: "4px 0", overflowWrap: "anywhere" }}>{cleanText(c)}</li>)}
      </ul>
    </div>
  );
}

/** Distance split by speed band, as horizontal bars with metres and share. */
export function ZoneBars({ zones, title = "Distance by speed zone" }) {
  const z = obj(zones);
  const total = SPEED_ZONES.reduce((n, s) => n + (isNum(z[s.key]) ? Number(z[s.key]) : 0), 0);
  const extra = Object.keys(z).filter((k) => !SPEED_ZONES.some((s) => s.key === k));
  const rows = [...SPEED_ZONES, ...extra.map((k) => ({ key: k, label: titleCase(k), band: "", color: "var(--info)" }))];
  return (
    <div className="card stack" style={{ "--gap": "14px" }}>
      <div className="spread">
        <b>{title}</b>
        <span className="tiny muted">{total > 0 ? `${num(total)} m total` : "No movement measured"}</span>
      </div>
      <div className="zone-bars">
        {rows.map((s) => {
          const value = isNum(z[s.key]) ? Number(z[s.key]) : null;
          const pctValue = total > 0 && value != null ? (value / total) * 100 : 0;
          return (
            <div key={s.key} className="zone">
              <span className="text-2" style={{ minWidth: 0 }}>
                <span className="truncate" style={{ display: "block" }}>{s.label}</span>
                {s.band && <span className="tiny muted">{s.band}</span>}
              </span>
              <div className="meter"><div style={{ width: `${pctValue}%`, background: s.color }} /></div>
              <span className="mono small" style={{ textAlign: "right" }}>
                {value == null ? "-" : `${num(value)} m`}
                <span className="tiny muted" style={{ display: "block" }}>{total > 0 && value != null ? `${Math.round(pctValue)}%` : ""}</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** FC-style attributes with bars; estimated attributes get a dashed marker and an asterisk. */
export function RatingsPanel({ ratings }) {
  const r = obj(ratings);
  const estimated = new Set(list(r.estimated));
  return (
    <div className="card stack" style={{ "--gap": "16px" }}>
      <div className="spread">
        <div>
          <div className="eyebrow">ScoutAI ratings</div>
          <h3 className="section-title" style={{ marginTop: 4 }}>
            Overall {isNum(r.overall) ? r.overall : "-"}
            {r.position && r.position !== "--" ? <span className="muted"> · {r.position}</span> : null}
          </h3>
        </div>
        <span className="tiny muted">0-99 scale · 30 floor · * = limited evidence</span>
      </div>
      <div className="stack corner-bars" style={{ "--gap": "10px" }}>
        {ATTRIBUTES.map((a) => (
          <div key={a.key} className="bar" style={{ gridTemplateColumns: "minmax(90px, 130px) 1fr 44px" }}>
            <span className="text-2">
              <b style={{ color: "var(--text)" }}>{a.key}</b> {a.label}
            </span>
            <ProgressBar percent={isNum(r[a.key]) ? Number(r[a.key]) : 0} />
            <b className="mono" title={estimated.has(a.key) ? "Estimated - limited evidence in this clip" : undefined}>
              {isNum(r[a.key]) ? r[a.key] : "-"}{estimated.has(a.key) ? "*" : ""}
            </b>
          </div>
        ))}
      </div>
      {estimated.size > 0 && (
        <span className="tiny muted">
          * {[...estimated].join(", ")} had limited evidence in this clip and lean on neutral, league-typical values.
        </span>
      )}
    </div>
  );
}
