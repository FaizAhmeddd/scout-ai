import {
  ArrowRight,
  Bot,
  Crosshair,
  Cpu,
  Gauge,
  Map,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";

import {
  AnimatedHeadline, CountUp, Reveal, ScanFrame, spotlightHandlers, Stagger, StaggerItem, Tilt,
} from "../components/fx/Motion.jsx";
import TrackingField from "../components/fx/TrackingField.jsx";
import Brand from "../components/layout/Brand.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const PIPELINE = [
  { title: "Pose tracking", text: "Every person and their 17 body keypoints per frame, tracked with appearance re-identification." },
  { title: "Ball & pitch", text: "A football-trained ball detector and 32 pitch landmarks calibrate every frame." },
  { title: "Who's playing", text: "Coaches, stewards and crowd removed; teams split by shirt-colour histograms." },
  { title: "Identity repair", text: "Appearance ReID re-links players after occlusions and re-entries; swaps between opponents are cut." },
  { title: "Physical metrics", text: "Distance, FIFA speed zones, sprints, accelerations, cadence, possession." },
  { title: "AI event analysis", text: "An agentic video AI watches the clip and logs every on-ball event." },
  { title: "Fusion & report", text: "FC-style ratings, annotated video, 9+ graphs and a scouting report." },
];

const FEATURES = [
  { icon: ScanLine, title: "Pose-level tracking", text: "Skeletons for every player, not just boxes - enabling running cadence, posture and ankle-precise ball control." },
  { icon: Map, title: "Automatic pitch calibration", text: "No manual clicking: pitch landmarks give real metres, a live mini-map and true pitch heatmaps." },
  { icon: Users, title: "Team or single player", text: "Pick a team, or click one player's thumbnail - the whole analysis focuses on them." },
  { icon: Bot, title: "Agentic event counting", text: "Passes, dribbles, shots, tackles, duels, interceptions - timestamped, with success and confidence." },
  { icon: Gauge, title: "Explainable ratings", text: "PAC / SHO / PAS / DRI / DEF / PHY from documented formulas with small-sample shrinkage." },
  { icon: ShieldCheck, title: "Honest by design", text: "Every report states its geometry, coverage and caveats - no invented numbers when evidence is thin." },
];

const STATS = [
  { value: 17, unit: "pts", label: "body keypoints tracked per player, every frame" },
  { value: 32, unit: "pts", label: "pitch landmarks for automatic calibration" },
  { value: 512, unit: "dim", label: "appearance signature keeping player IDs stable" },
  { value: 30, unit: "+", label: "match events and metrics per player report" },
];

const STACK = ["Pose estimation", "Multi-object tracking", "Appearance re-identification", "Automatic pitch calibration", "Agentic video AI", "Computer vision", "FastAPI", "MongoDB", "React"];

export default function Landing() {
  const { user } = useAuth();
  const primary = user ? { to: "/app/library", label: "Open workspace" } : { to: "/signup", label: "Create free account" };

  return (
    <>
      <motion.div
        className="container"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <nav className="public-nav">
          <Brand />
          <div className="row">
            {user ? (
              <Link className="btn primary" to="/app/library">
                Workspace <ArrowRight size={16} />
              </Link>
            ) : (
              <>
                <Link className="btn ghost" to="/login">Sign in</Link>
                <Link className="btn primary" to="/signup">Get started</Link>
              </>
            )}
          </div>
        </nav>
      </motion.div>

      <section className="hero">
        <TrackingField className="hero-field" />
        <div className="container hero-grid">
          <div>
            <motion.div className="eyebrow" initial={{ opacity: 0, letterSpacing: "0.4em" }} animate={{ opacity: 1, letterSpacing: "0.14em" }} transition={{ duration: 0.9 }}>
              AI performance analysis from broadcast video
            </motion.div>
            <AnimatedHeadline
              className="hero-title"
              parts={["Upload a match.", "\n", "Get a", { text: "scout's report", accent: true }, "\n", "in minutes."]}
            />
            <Reveal delay={0.7}>
              <p className="lead">
                Computer vision tracks every player's body, the ball and the pitch. Agentic video AI counts every
                pass, dribble and duel. The result: an annotated video, analysis graphs and FC-style ratings - for a
                whole team or one player.
              </p>
            </Reveal>
            <Reveal delay={0.85}>
              <div className="row" style={{ marginTop: 28 }}>
                <Link className="btn primary lg" to={primary.to}>
                  {primary.label} <ArrowRight size={18} />
                </Link>
                <a className="btn lg" href="#how-it-works">See how it works</a>
              </div>
            </Reveal>
            <Stagger className="trust-row" inView={false}>
              {["17-keypoint pose", "Real pitch metres", "Agentic video AI", "Team & player modes"].map((t) => (
                <StaggerItem key={t} className="badge">
                  <Sparkles size={12} /> {t}
                </StaggerItem>
              ))}
            </Stagger>
          </div>

          <motion.div
            className="hero-visual"
            initial={{ opacity: 0, x: 40, rotateY: -12 }}
            animate={{ opacity: 1, x: 0, rotateY: 0 }}
            transition={{ duration: 1.1, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
            style={{ perspective: 1200 }}
          >
            <div className="frame energy">
              <ScanFrame label="TRACKING · 22 PLAYERS">
                <img src="/showcase/annotated-frame.jpg" alt="Annotated match frame with pose skeletons, focus player and minimap" />
              </ScanFrame>
            </div>
            <div className="floating-card float">
              <Tilt max={14}>
                <img src="/showcase/player-card.png" alt="Generated player rating card" style={{ borderRadius: 18 }} />
              </Tilt>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 40 }}>
        <div className="container">
          <Stagger className="stat-band">
            {STATS.map((s) => (
              <StaggerItem key={s.label}>
                <div className="big">
                  <CountUp value={s.value} />
                  <small>{s.unit}</small>
                </div>
                <div className="small text-2">{s.label}</div>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="section" id="how-it-works">
        <div className="container">
          <Reveal className="section-head">
            <div className="eyebrow">The pipeline</div>
            <h2>Seven stages from raw video to scouting report</h2>
            <p>Each stage is a standalone, tested component - configured from one file and shared by the command line and this web app.</p>
          </Reveal>
          <Stagger className="pipeline">
            {PIPELINE.map((step) => (
              <StaggerItem key={step.title} className="step spotlight">
                <h4>{step.title}</h4>
                <p>{step.text}</p>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="ai-sees">
            <Reveal>
              <div className="eyebrow">What the AI sees</div>
              <h2 style={{ fontSize: 32, fontWeight: 800, marginTop: 8 }}>Every player, every frame, one identity</h2>
              <p className="text-2" style={{ marginTop: 12 }}>
                Each player keeps a stable ID through crossings, duels and re-entries thanks to appearance
                re-identification. Movement becomes real metres on a calibrated pitch, and the ball is followed
                from foot to foot.
              </p>
              <div className="row" style={{ marginTop: 18 }}>
                {["Stable IDs", "Passing lanes", "Live speed", "Ball possession"].map((t) => (
                  <span key={t} className="badge accent"><Crosshair size={12} /> {t}</span>
                ))}
              </div>
            </Reveal>
            <Reveal delay={0.15}>
              <div className="field-panel energy" style={{ aspectRatio: "16 / 10" }}>
                <ScanFrame label="LIVE ID TRACKING">
                  <div style={{ position: "relative", aspectRatio: "16 / 10" }}>
                    <TrackingField />
                  </div>
                </ScanFrame>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <Reveal className="section-head">
            <div className="eyebrow">Capabilities</div>
            <h2>Built for analysts, explainable for coaches</h2>
          </Reveal>
          <Stagger className="grid" style={{ "--min": "300px" }}>
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <StaggerItem key={title}>
                <div className="card feature spotlight" style={{ height: "100%" }} {...spotlightHandlers()}>
                  <div className="icon">
                    <Icon size={20} />
                  </div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <Reveal className="section-head">
            <div className="eyebrow">Real output</div>
            <h2>What you get back</h2>
            <p>Generated by this system from a 30-second Bundesliga clip - nothing mocked.</p>
          </Reveal>
          <Stagger className="showcase">
            {[
              { src: "/showcase/annotated-frame-2.jpg", caption: "Pose-annotated video with team colours, focus highlight, HUD and pitch mini-map", label: "ANNOTATED VIDEO" },
              { src: "/showcase/heatmap.png", caption: "Heatmap on real pitch coordinates (automatic calibration)", label: "HEATMAP" },
              { src: "/showcase/radar.png", caption: "FC-style attribute radar fusing tracking and AI-detected events", label: "RATINGS" },
            ].map((item) => (
              <StaggerItem key={item.src}>
                <figure>
                  <ScanFrame label={item.label}>
                    <img src={item.src} alt={item.caption} />
                  </ScanFrame>
                  <figcaption>{item.caption}</figcaption>
                </figure>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="grid" style={{ "--min": "320px", alignItems: "center" }}>
            <Reveal>
              <div className="eyebrow">Under the hood</div>
              <h2 style={{ fontSize: 28, marginTop: 8 }}>Production-minded architecture</h2>
              <p className="text-2" style={{ marginTop: 10 }}>
                FastAPI serves a MongoDB-backed workspace with secure accounts. Long-running computer vision runs in
                a background worker with live progress; expensive tracking is cached, so re-analysing
                another player of the same video takes seconds.
              </p>
            </Reveal>
            <Stagger className="row" style={{ "--gap": "8px" }}>
              {STACK.map((s) => (
                <StaggerItem key={s} className="badge">
                  <Cpu size={12} /> {s}
                </StaggerItem>
              ))}
            </Stagger>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <Reveal>
            <div className="cta-band energy spread">
              <div>
                <h2 style={{ fontSize: 26 }}>Ready to analyse your first match?</h2>
                <p className="text-2" style={{ marginTop: 6 }}>
                  Upload a clip, pick a team or a player, and watch the analysis build live.
                </p>
              </div>
              <Link className="btn primary lg" to={primary.to}>
                <Crosshair size={18} /> {primary.label}
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="footer">
        <div className="container spread">
          <span>ScoutAI - pose tracking, pitch calibration and agentic video understanding.</span>
          <span>Built with FastAPI, MongoDB and React</span>
        </div>
      </footer>
    </>
  );
}
