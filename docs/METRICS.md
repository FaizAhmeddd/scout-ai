# How performance is measured

Every number in a report comes from one of three sources: **tracking** (computer vision), **AI event analysis**
(agentic video understanding), or **fusion** of both. Reports state which geometry was used and list caveats.
Config values below are in `backend/config/config.yaml`.

## Tracking and positions

- Players, goalkeepers, referees and the ball are detected every frame; players keep a stable ID through crossings
  and occlusions via motion + appearance (ReID) matching; broken fragments are re-linked afterwards.
- Pixels become metres through the best available geometry: automatic pitch calibration (32 pitch landmarks →
  homography, per frame) → pose-height scale (a player ≈ 1.75 m tall, ±15%) as the fallback.
- Positions are cleaned before use: median filter + Savitzky-Golay smoothing, tracks split at teleports/scene cuts.

## Physical metrics (per player, only while on screen)

| Metric | Definition |
|---|---|
| Distance, m/min | Sum of smoothed step lengths; per tracked minute |
| Top speed | Highest speed **sustained over 1 s** (`kinematics.top_speed_window_s`); capped at 38 km/h |
| Speed zones | FIFA EPTS bands: walking 0–7, jogging 7–15, running 15–20, high-speed 20–25, sprint 25+ km/h |
| High-intensity distance | Distance covered above 20 km/h; share of total |
| Sprints | ≥ 25 km/h for ≥ 1 s (start, end, duration, peak, distance logged) |
| Accelerations / decelerations | ≥ 3 m/s² sustained ≥ 0.5 s |
| Cadence, trunk lean | Ankle-keypoint oscillation (while ≥ 9 km/h); shoulder–hip angle |
| Ball control, touches | A player controls the ball when an ankle is within 0.55 body-heights of it for ≥ 3 frames; one possession spell = one touch |
| Team possession | Share of clearly-controlled frames per team (flagged indicative below 20 s of control) |

Broadcast cameras follow the ball, so off-ball running is under-counted; physical metrics cover on-screen time only.

## AI event analysis

An agentic video model watches the clip with the target context (team colour, reference crop of the player,
on-screen windows) and returns a **timestamped event log**: passes (short/long, progressive, key, assists),
dribbles, shots (on target, goals), crosses, tackles, interceptions, clearances, blocks, duels (ground/aerial),
recoveries, possession lost, fouls, cards, saves — each with success and confidence. Events are matched to the
tracked position at their timestamp (`fusion/report_builder.py`). Counts are model estimates and say so.

## Ratings (FC-style, 0–99)

Built in `engine/fusion/rating_model.py`. Rates are normalised per 10 on-screen minutes and **shrunk toward
league-typical priors** so a handful of events cannot produce extreme scores; attributes with too little evidence
are marked `*` (estimated).

| Attribute | Main inputs |
|---|---|
| PAC | Top speed (75%) + sprints per 10 min (25%) |
| SHO | Shot volume (35%), on-target rate (45%), technical score (20%), +6 per goal |
| PAS | Pass + cross accuracy (55%), key passes (15%), progressive passes (15%), pass volume (15%), +5 per assist |
| DRI | Dribble success (45%), dribble volume (25%), technical score (30%) |
| DEF | Defensive actions (45%), tackle success (30%), duel success (25%) |
| PHY | Distance/min (45%), high-intensity share (25%), accelerations (15%), duel success (15%) |

**Overall** = position-weighted attributes (ATT / MID / DEF weight tables), blended 25% with the AI analyst's
match rating. Without AI events, technical attributes are neutral estimates. In **team mode**, AI events are counted
for the team as a whole, so per-player SHO/PAS/DRI/DEF are estimates; PAC and PHY are measured per player.

## Limitations (always shown in the report)

Clip length and camera coverage bound every metric; replays and close-ups are excluded when calibration fails;
possession from a short clip is indicative; ratings describe the clip, not a season.
