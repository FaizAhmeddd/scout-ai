import { Bot, Play, Shirt, User, UsersRound, Video } from "lucide-react";
import { useEffect, useState } from "react";

import { assetUrl } from "../../services/apiClient.js";
import { isNum, list } from "../../utils/format.js";
import { Stagger, StaggerItem } from "../fx/Motion.jsx";
import { Toggle } from "../ui/Primitives.jsx";
import { Notice } from "../ui/States.jsx";

// Below this on-screen time the backend marks pace and physical ratings as estimates (rating_model.py).
const SHORT_ON_SCREEN_S = 20;

function PlayerThumb({ player }) {
  const [failed, setFailed] = useState(false);
  if (!player.thumbnail_url || failed) {
    return <div className="no-thumb"><User size={28} /></div>;
  }
  return <img src={assetUrl(player.thumbnail_url)} alt={`Player ${player.number}`} loading="lazy" onError={() => setFailed(true)} />;
}

export default function TargetPicker({ teams: rawTeams, onRun, busy }) {
  const teams = list(rawTeams);
  const [teamNumber, setTeamNumber] = useState(teams[0]?.number ?? 1);
  const [playerNumber, setPlayerNumber] = useState(null);
  const [jersey, setJersey] = useState("");
  const [name, setName] = useState("");
  const [useGemini, setUseGemini] = useState(true);
  const [renderVideo, setRenderVideo] = useState(true);
  const team = teams.find((t) => t.number === teamNumber);
  const players = list(team?.players);
  const selected = players.find((p) => p.number === playerNumber);

  // Keep the selection valid if the team list changes (e.g. after re-running detection).
  useEffect(() => {
    if (teams.length && !teams.some((t) => t.number === teamNumber)) {
      setTeamNumber(teams[0].number);
      setPlayerNumber(null);
    }
  }, [teams, teamNumber]);

  const run = () => {
    if (busy || !team) return;
    onRun({
      team: teamNumber,
      player: selected ? playerNumber : null,
      jersey_number: selected && jersey !== "" ? Number(jersey) : null,
      player_name: selected ? name.trim() : "",
      use_gemini: useGemini,
      render_video: renderVideo,
    });
  };

  return (
    <div className="stack" style={{ "--gap": "24px" }}>
      <div className="stack" style={{ "--gap": "12px" }}>
        <div className="eyebrow">Step 1 · Team</div>
        <div className="grid" style={{ "--min": "220px" }}>
          {teams.map((t) => (
            <button
              key={t.number}
              className={`team-option${t.number === teamNumber ? " selected" : ""}`}
              onClick={() => {
                setTeamNumber(t.number);
                setPlayerNumber(null);
              }}
            >
              <span className="kit" style={{ background: t.color_hex || "var(--line-2)" }} />
              <span style={{ minWidth: 0 }}>
                <span className="truncate" style={{ display: "block", fontWeight: 700 }}>Team {t.number} · {t.color_name || "unknown"} kit</span>
                <span className="small muted">
                  {list(t.players).length ? `${list(t.players).length} players tracked` : "No individual players tracked"}
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="stack" style={{ "--gap": "12px" }}>
        <div className="spread">
          <div className="eyebrow">Step 2 · Whole team or one player</div>
          <span className="tiny muted">Seconds = time on screen. Longer = more reliable metrics.</span>
        </div>
        <Stagger className="player-grid" inView={false} animateKey={teamNumber}>
          <StaggerItem><button className={`player-tile whole${playerNumber === null ? " selected" : ""}`} onClick={() => setPlayerNumber(null)}>
            <span className="stack" style={{ "--gap": "8px", alignItems: "center" }}>
              <UsersRound size={28} color={team?.color_hex} />
              Whole team
            </span>
          </button></StaggerItem>
          {players.map((p) => {
            const short = isNum(p.on_screen_s) && p.on_screen_s < SHORT_ON_SCREEN_S;
            return (
              <StaggerItem key={p.number}><button
                className={`player-tile${p.number === playerNumber ? " selected" : ""}`}
                onClick={() => setPlayerNumber(p.number)}
                title={`Player ${p.number}${isNum(p.on_screen_s) ? ` · ${Math.round(p.on_screen_s)} s on screen` : ""}`}
              >
                <PlayerThumb player={p} />
                <div className="meta">
                  <b>#{p.number}</b> · {isNum(p.on_screen_s) ? `${Number(p.on_screen_s).toFixed(0)}s` : "-"}
                  {short && <span className="warn-tag" style={{ display: "block" }}>limited footage</span>}
                </div>
              </button></StaggerItem>
            );
          })}
        </Stagger>
        {players.length === 0 && (
          <Notice title="No individual players with enough screen time in this team">
            Each player must be visible for at least a couple of seconds to be listed. You can still analyse the whole team
            - possession, team events and every tracked movement are included.
          </Notice>
        )}
        {selected && isNum(selected.on_screen_s) && selected.on_screen_s < SHORT_ON_SCREEN_S && (
          <Notice tone="warn" title={`Player #${selected.number} is on screen for only ${Math.round(selected.on_screen_s)} s`}>
            The report will still be generated, but pace and physical ratings need around {SHORT_ON_SCREEN_S} s of footage and
            will be marked as estimates. Pick a player with more screen time for the most reliable numbers.
          </Notice>
        )}
      </div>

      <div className="stack" style={{ "--gap": "12px" }}>
        <div className="eyebrow">Step 3 · Options</div>
        {selected && (
          <div className="grid" style={{ "--min": "220px" }}>
            <div className="field">
              <label htmlFor="jersey">Jersey number (helps the AI find the player)</label>
              <div className="input-icon">
                <Shirt size={16} />
                <input id="jersey" className="input" inputMode="numeric" placeholder="e.g. 10" value={jersey}
                  onChange={(e) => setJersey(e.target.value.replace(/\D/g, "").slice(0, 2))} />
              </div>
            </div>
            <div className="field">
              <label htmlFor="pname">Player name for the report</label>
              <input id="pname" className="input" placeholder="Optional" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
            </div>
          </div>
        )}
        <div className="row" style={{ "--gap": "24px" }}>
          <span className="row" style={{ "--gap": "8px", flexWrap: "nowrap" }}>
            <Bot size={16} color="var(--accent)" style={{ flex: "none" }} />
            <Toggle checked={useGemini} onChange={setUseGemini} label="AI event analysis (passes, dribbles, duels)" />
          </span>
          <span className="row" style={{ "--gap": "8px", flexWrap: "nowrap" }}>
            <Video size={16} color="var(--accent)" style={{ flex: "none" }} />
            <Toggle checked={renderVideo} onChange={setRenderVideo} label="Render annotated pose video" />
          </span>
        </div>
        {!useGemini && (
          <Notice>
            Without AI event analysis the report still includes every tracking metric (distance, speed zones, sprints,
            accelerations, cadence, ball possession), but no passes, shots or duels - technical ratings become neutral estimates.
          </Notice>
        )}
      </div>

      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn primary lg" disabled={busy || !team} onClick={run}>
          <Play size={18} />
          {busy ? "Starting..." : selected ? `Analyse player #${playerNumber}` : `Analyse team ${teamNumber}`}
        </button>
      </div>
    </div>
  );
}
