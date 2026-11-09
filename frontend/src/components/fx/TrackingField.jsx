import { useEffect, useRef } from "react";

const TEAM_COLORS = ["#4fc3f7", "#e8eef5"];
const ACCENT = "#ffe600";
const PLAYERS_PER_TEAM = 11;
const TRAIL = 22;

function createPlayers(width, height) {
  const players = [];
  for (let team = 0; team < 2; team++) {
    for (let i = 0; i < PLAYERS_PER_TEAM; i++) {
      const homeX = team === 0 ? 0.12 + Math.random() * 0.38 : 0.5 + Math.random() * 0.38;
      const homeY = 0.12 + Math.random() * 0.76;
      players.push({
        id: team * 11 + i + 1,
        team,
        x: homeX * width,
        y: homeY * height,
        vx: 0,
        vy: 0,
        home: { x: homeX, y: homeY },
        target: { x: homeX * width, y: homeY * height },
        trail: [],
      });
    }
  }
  return players;
}

function drawPitch(ctx, w, h) {
  ctx.save();
  ctx.strokeStyle = "rgba(34, 197, 94, 0.16)";
  ctx.lineWidth = 1;
  const m = 18;
  ctx.strokeRect(m, m, w - 2 * m, h - 2 * m);
  ctx.beginPath();
  ctx.moveTo(w / 2, m);
  ctx.lineTo(w / 2, h - m);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(w / 2, h / 2, Math.min(w, h) * 0.12, 0, Math.PI * 2);
  ctx.stroke();
  const boxH = h * 0.5;
  const boxW = w * 0.12;
  ctx.strokeRect(m, (h - boxH) / 2, boxW, boxH);
  ctx.strokeRect(w - m - boxW, (h - boxH) / 2, boxW, boxH);
  ctx.restore();
}

function corners(ctx, x, y, s, color) {
  const l = s * 0.45;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  for (const [cx, cy, dx, dy] of [[x - s, y - s, 1, 1], [x + s, y - s, -1, 1], [x - s, y + s, 1, -1], [x + s, y + s, -1, -1]]) {
    ctx.moveTo(cx, cy + dy * l);
    ctx.lineTo(cx, cy);
    ctx.lineTo(cx + dx * l, cy);
  }
  ctx.stroke();
}

/** Ambient "what the AI sees" canvas: players tracked with boxes, IDs, trails, a ball and passing lanes. */
export default function TrackingField({ className = "", density = 1, showLabels = true }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let players = [];
    let ball = { x: 0, y: 0, from: null, to: null, t: 1, holder: null };
    let focus = null;
    let frame = 0;
    let raf = 0;
    let visible = true;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      players = createPlayers(width, height).slice(0, Math.round(PLAYERS_PER_TEAM * 2 * density));
      ball.holder = players[Math.floor(Math.random() * players.length)];
      ball.x = ball.holder.x;
      ball.y = ball.holder.y;
      focus = players[3];
    };

    const pass = () => {
      const mates = players.filter((p) => p.team === ball.holder.team && p !== ball.holder);
      const next = mates[Math.floor(Math.random() * mates.length)];
      ball.from = { x: ball.holder.x, y: ball.holder.y };
      ball.to = next;
      ball.t = 0;
      ball.holder = null;
    };

    const step = () => {
      frame++;
      for (const p of players) {
        if (frame % 90 === p.id % 90) {
          const drift = 0.08;
          p.target.x = (p.home.x + (Math.random() - 0.5) * drift * 2) * width;
          p.target.y = (p.home.y + (Math.random() - 0.5) * drift * 3) * height;
        }
        if (ball.holder && ball.holder !== p && p.team !== ball.holder.team && Math.hypot(p.x - ball.x, p.y - ball.y) < 120) {
          p.target.x = ball.x;
          p.target.y = ball.y;
        }
        const ax = (p.target.x - p.x) * 0.0016;
        const ay = (p.target.y - p.y) * 0.0016;
        p.vx = (p.vx + ax) * 0.94;
        p.vy = (p.vy + ay) * 0.94;
        p.x += p.vx;
        p.y += p.vy;
        if (frame % 2 === 0) {
          p.trail.push({ x: p.x, y: p.y });
          if (p.trail.length > TRAIL) p.trail.shift();
        }
      }
      if (ball.holder) {
        ball.x += (ball.holder.x + 6 - ball.x) * 0.3;
        ball.y += (ball.holder.y + 6 - ball.y) * 0.3;
        if (frame % 110 === 0) pass();
      } else if (ball.to) {
        ball.t = Math.min(1, ball.t + 0.022);
        const e = 1 - (1 - ball.t) ** 3;
        ball.x = ball.from.x + (ball.to.x - ball.from.x) * e;
        ball.y = ball.from.y + (ball.to.y - ball.from.y) * e - Math.sin(Math.PI * ball.t) * 18;
        if (ball.t >= 1) {
          ball.holder = ball.to;
          if (Math.random() < 0.35) focus = ball.holder;
        }
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      drawPitch(ctx, width, height);

      if (focus) {
        ctx.save();
        ctx.setLineDash([3, 5]);
        ctx.strokeStyle = "rgba(255, 230, 0, 0.22)";
        for (const p of players) {
          if (p.team === focus.team && p !== focus && Math.hypot(p.x - focus.x, p.y - focus.y) < 170) {
            ctx.beginPath();
            ctx.moveTo(focus.x, focus.y);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          }
        }
        ctx.restore();
      }

      for (const p of players) {
        const color = TEAM_COLORS[p.team];
        for (let i = 1; i < p.trail.length; i++) {
          ctx.strokeStyle = p === focus ? `rgba(255,230,0,${(i / p.trail.length) * 0.6})` : `rgba(148,163,184,${(i / p.trail.length) * 0.25})`;
          ctx.lineWidth = p === focus ? 2 : 1;
          ctx.beginPath();
          ctx.moveTo(p.trail[i - 1].x, p.trail[i - 1].y);
          ctx.lineTo(p.trail[i].x, p.trail[i].y);
          ctx.stroke();
        }
        const isFocus = p === focus;
        if (isFocus) {
          const pulse = 14 + Math.sin(frame / 8) * 3;
          ctx.strokeStyle = "rgba(255, 230, 0, 0.6)";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(p.x, p.y, pulse, 0, Math.PI * 2);
          ctx.stroke();
        }
        corners(ctx, p.x, p.y, isFocus ? 11 : 8, isFocus ? ACCENT : `${color}99`);
        ctx.fillStyle = isFocus ? ACCENT : color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, isFocus ? 3.6 : 2.6, 0, Math.PI * 2);
        ctx.fill();
        if (showLabels) {
          ctx.font = "600 9px 'JetBrains Mono', monospace";
          ctx.fillStyle = isFocus ? ACCENT : "rgba(180, 192, 207, 0.75)";
          ctx.fillText(isFocus ? `ID ${String(p.id).padStart(2, "0")} · ${Math.min(32, 6 + Math.hypot(p.vx, p.vy) * 8).toFixed(1)} km/h` : String(p.id).padStart(2, "0"), p.x + 12, p.y - 9);
        }
      }

      ctx.save();
      ctx.shadowColor = ACCENT;
      ctx.shadowBlur = 12;
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(ball.x, ball.y, 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    };

    const loop = () => {
      if (visible) {
        step();
        draw();
      }
      raf = requestAnimationFrame(loop);
    };

    resize();
    if (reduced) {
      for (let i = 0; i < 120; i++) step();
      draw();
    } else {
      raf = requestAnimationFrame(loop);
    }

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    observer.observe(canvas);
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [density, showLabels]);

  return <canvas ref={canvasRef} className={`tracking-field ${className}`} aria-hidden="true" />;
}
