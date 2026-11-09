import { Activity, Bot, Crosshair, Footprints, Gauge, Map, Ruler, ShieldCheck, Trophy, Zap } from "lucide-react";

import { list } from "../../utils/format.js";
import { SPEED_ZONES } from "./ResultBlocks.jsx";

/*
 * Short, scannable explanation of every metric and rating. Every threshold below mirrors the backend:
 * engine/metrics/kinematics.py + config/config.yaml (kinematics), metrics/pose_metrics.py, metrics/possession.py,
 * fusion/event_counts.py, fusion/rating_model.py and fusion/report_builder.py.
 */

const GEOMETRY_TEXT = {
  pitch_keypoints: "Automatic pitch calibration: pitch lines are found every frame and mapped to metres on a 105 × 68 m pitch. Close-ups and replays are excluded.",
  homography: "Manual pitch calibration: fixed reference points map the screen to metres.",
  pose_scale: "No pitch calibration: players are scaled against an average height (1.75 m). Accuracy ≈ ±15%; maps are camera-relative.",
};

function Section({ icon: Icon, title, children }) {
  return (
    <div className="card method-card stack" style={{ "--gap": "10px" }}>
      <h4>
        <Icon size={16} color="var(--accent)" /> {title}
      </h4>
      {children}
    </div>
  );
}

function Formula({ title, children }) {
  return (
    <div className="stack" style={{ "--gap": "6px" }}>
      <b className="small">{title}</b>
      <div className="formula">{children}</div>
    </div>
  );
}

export default function Methodology({ mode = "player", geometryMode, estimated, aiAvailable = true }) {
  const est = list(estimated);
  return (
    <div className="stack" style={{ "--gap": "16px" }}>
      <p className="small text-2" style={{ maxWidth: 820 }}>
        Two sources feed every number: <b>Tracking</b> (movement, pose, possession - measured from the video) and the{" "}
        <b>AI analyst</b> (passes, dribbles, shots, duels - logged like a scout). They are fused into the ratings.
      </p>

      <div className="method-grid">
        <Section icon={Activity} title="1 · Tracking">
          <ul>
            <li><b>17 body keypoints</b> per player, every frame</li>
            <li>Appearance matching keeps IDs through crossings and cuts</li>
            <li>Teams split by shirt colour; referees excluded</li>
            <li>Under <b>2 s</b> on screen = fragment, hidden from team tables</li>
          </ul>
        </Section>

        <Section icon={Ruler} title="2 · Pixels → metres">
          <p>{GEOMETRY_TEXT[geometryMode] ?? GEOMETRY_TEXT.pitch_keypoints}</p>
          <ul>
            <li>Outliers removed, path smoothed over <b>0.6 s</b></li>
            <li>Steps above <b>38 km/h</b> discarded</li>
            <li>No distance added across gaps over <b>0.6 s</b></li>
          </ul>
        </Section>

        <Section icon={Gauge} title="3 · Distance & speed">
          <ul>
            <li><b>Distance</b> - on-screen path only</li>
            <li><b>Metres/min</b> - distance ÷ time tracked (fairest comparison)</li>
            <li><b>Average speed</b> - includes standing and walking</li>
            <li><b>Top speed</b> - best speed held for <b>1 s</b>, not a spike</li>
          </ul>
        </Section>

        <Section icon={Footprints} title="4 · Speed zones">
          <ul>
            {SPEED_ZONES.map((z) => (
              <li key={z.key}><b>{z.label}</b> - {z.band}</li>
            ))}
          </ul>
          <p><b>High-intensity</b> = everything above 20 km/h</p>
        </Section>

        <Section icon={Zap} title="5 · Sprints & accelerations">
          <ul>
            <li><b>Sprint</b> - ≥ <b>25 km/h</b> for ≥ <b>1 s</b></li>
            <li><b>Acceleration</b> - ≥ <b>3 m/s²</b> for ≥ 0.5 s</li>
            <li><b>Deceleration</b> - braking of ≥ <b>3 m/s²</b> for ≥ 0.5 s</li>
          </ul>
        </Section>

        <Section icon={Activity} title="6 · Biomechanics">
          <ul>
            <li><b>Cadence</b> - steps/min above 9 km/h (valid 90-260)</li>
            <li><b>Trunk lean</b> - median torso angle from vertical while running</li>
            <li><b>Visibility</b> - share of keypoints seen clearly</li>
          </ul>
        </Section>

        <Section icon={Crosshair} title="7 · Ball possession">
          <ul>
            <li>Ball belongs to the nearest player whose <b>foot</b> is within ~½ body-height</li>
            <li>Control changes after <b>3 consecutive frames</b></li>
            <li><b>Control time</b> and <b>touches</b> (separate times control was gained)</li>
            {mode === "team" && <li><b>Team possession</b> - share of time each team last had the ball</li>}
          </ul>
        </Section>

        <Section icon={Bot} title="8 · AI match events">
          {!aiAvailable && <p><b>AI event analysis did not run for this report.</b></p>}
          <ul>
            <li>Each action logged with time, type, outcome, player and confidence</li>
            <li><b>Success</b> = pass/cross completed, shot on target, dribble won, tackle/duel won</li>
            <li><b>Progressive pass</b> ≈ 10 m+ towards goal · <b>Key pass</b> = leads to a shot</li>
            <li><b>Defensive actions</b> = tackles won + interceptions + clearances + blocks + recoveries</li>
            <li>Events matched to tracked position (±1 s)</li>
          </ul>
        </Section>
      </div>

      <Section icon={Trophy} title="9 · Ratings (PAC · SHO · PAS · DRI · DEF · PHY · OVR)">
        <p>
          Each input is scaled across a benchmark range (40-95), then weighted. Volumes are <b>per 10 on-screen minutes</b>; rates are{" "}
          <b>shrunk towards league averages</b> so two lucky passes can't give a 99.
        </p>
        <div className="grid" style={{ "--min": "300px", "--gap": "12px" }}>
          <Formula title="PAC · Pace (tracking)">75% top speed (18 → 34 km/h) + 25% sprints /10 min (0 → 5)</Formula>
          <Formula title="PHY · Physical (tracking + duels)">45% m/min (50 → 130) + 25% high-intensity share (2% → 18%) + 15% accel/decel /10 min (0 → 14) + 15% duel wins (30% → 70%)</Formula>
          <Formula title="SHO · Shooting (events)">35% shots /10 min (0 → 3) + 45% on-target rate (15% → 75%) + 20% technical + 6 per goal</Formula>
          <Formula title="PAS · Passing (events)">55% accuracy (55% → 93%) + 15% key passes + 15% progressive passes + 15% volume + 5 per assist</Formula>
          <Formula title="DRI · Dribbling (events)">45% success (25% → 80%) + 25% dribbles /10 min (0 → 4) + 30% technical</Formula>
          <Formula title="DEF · Defending (events)">45% defensive actions /10 min (0 → 6) + 30% tackle wins (30% → 80%) + 25% duel wins (30% → 70%)</Formula>
        </div>
        <ul>
          <li><b>Technical</b> = the AI analyst's 0-10 technical grade (3 → 9)</li>
          <li><b>*</b> = no evidence in the clip (neutral value). Without AI events SHO/PAS/DRI/DEF are estimates; under 20 s tracked, PAC/PHY too</li>
          <li>
            <b>OVR</b> = position-weighted: attackers shooting 30% + dribbling 25%; midfielders passing 30% + dribbling 20%;
            defenders defending 45% + physical 20%. The AI match rating adds 25% when available
          </li>
          {mode === "team" && <li>Team analyses count events for the whole team: per-player tables show only PAC and PHY</li>}
        </ul>
        {est.length > 0 && <p><b>This report:</b> {est.join(", ")} {est.length === 1 ? "is an estimate" : "are estimates"} (limited evidence).</p>}
      </Section>

      <div className="method-grid">
        <Section icon={Map} title="Scouting assessment">
          <ul>
            <li>Position, strengths, areas to improve, match rating <b>/10</b> (6.0 = average)</li>
            <li><b>Four-corner model</b> - technical, tactical, physical, mental, each 0-10</li>
          </ul>
        </Section>
        <Section icon={ShieldCheck} title="Confidence & limits">
          <ul>
            <li>Physical numbers cover <b>on-screen time only</b> - compare metres/min, not totals</li>
            <li>Every AI event carries <b>high / medium / low</b> confidence</li>
            <li>Ratings describe one clip; longer wide-angle clips are more reliable</li>
          </ul>
        </Section>
      </div>
    </div>
  );
}
