import { animate, motion, useInView, useMotionValue, useSpring, useTransform } from "motion/react";
import { useEffect, useRef, useState } from "react";

const EASE = [0.22, 1, 0.36, 1];

/** Fades and lifts its children into view the first time they scroll on screen. */
export function Reveal({ children, delay = 0, y = 24, className, style, as = "div" }) {
  const Component = motion[as];
  return (
    <Component
      className={className}
      style={style}
      initial={{ opacity: 0, y, filter: "blur(6px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.7, delay, ease: EASE }}
    >
      {children}
    </Component>
  );
}

const staggerParent = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const staggerChild = {
  hidden: { opacity: 0, y: 18, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.55, ease: EASE } },
};

/** Children wrapped in <StaggerItem> enter one after another. Re-animates when `animateKey` changes. */
export function Stagger({ children, className, style, animateKey, inView = true }) {
  return (
    <motion.div
      key={animateKey}
      className={className}
      style={style}
      variants={staggerParent}
      initial="hidden"
      {...(inView ? { whileInView: "show", viewport: { once: true, margin: "-40px" } } : { animate: "show" })}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className, style }) {
  return (
    <motion.div className={className} style={style} variants={staggerChild}>
      {children}
    </motion.div>
  );
}

/** Animates the leading number of a value ("38 m", "64", "1/1" stays as-is when not purely numeric). */
export function CountUp({ value, duration = 1.2 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const text = String(value ?? "");
  const match = text.match(/^(-?\d+(?:\.\d+)?)(.*)$/);
  const [display, setDisplay] = useState(match ? `0${match[2]}` : text);

  useEffect(() => {
    if (!match) {
      setDisplay(text);
      return undefined;
    }
    if (!inView) return undefined;
    const target = parseFloat(match[1]);
    const decimals = (match[1].split(".")[1] || "").length;
    const controls = animate(0, target, {
      duration,
      ease: EASE,
      onUpdate: (v) => setDisplay(`${v.toFixed(decimals)}${match[2]}`),
    });
    return () => controls.stop();
  }, [inView, text]);

  return <span ref={ref}>{display}</span>;
}

/** 3D tilt that follows the pointer, with a moving glare. */
export function Tilt({ children, max = 10, className, style }) {
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);
  const rotateX = useSpring(useTransform(y, [0, 1], [max, -max]), { stiffness: 200, damping: 20 });
  const rotateY = useSpring(useTransform(x, [0, 1], [-max, max]), { stiffness: 200, damping: 20 });
  const glareX = useTransform(x, [0, 1], ["0%", "100%"]);
  const glareY = useTransform(y, [0, 1], ["0%", "100%"]);

  return (
    <motion.div
      className={`tilt ${className ?? ""}`}
      style={{ ...style, rotateX, rotateY, transformPerspective: 900 }}
      onPointerMove={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        x.set((e.clientX - rect.left) / rect.width);
        y.set((e.clientY - rect.top) / rect.height);
      }}
      onPointerLeave={() => {
        x.set(0.5);
        y.set(0.5);
      }}
    >
      {children}
      <motion.span className="tilt-glare" style={{ "--gx": glareX, "--gy": glareY }} />
    </motion.div>
  );
}

/** Pointer-tracking radial highlight: put on any element with the `spotlight` class. */
export function spotlightHandlers() {
  return {
    onPointerMove: (e) => {
      const rect = e.currentTarget.getBoundingClientRect();
      e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
      e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
    },
  };
}

/** HUD frame around media: corner brackets, sweeping scan line and a live tag. */
export function ScanFrame({ children, label = "LIVE ANALYSIS", className = "" }) {
  return (
    <div className={`scan-frame ${className}`}>
      {children}
      <span className="scan-line" />
      <span className="hud-corner tl" />
      <span className="hud-corner tr" />
      <span className="hud-corner bl" />
      <span className="hud-corner br" />
      <span className="hud-tag">
        <span className="rec-dot" /> {label}
      </span>
    </div>
  );
}

/** Word-by-word headline entrance. Pass an array of strings or {text, accent} parts. */
export function AnimatedHeadline({ parts, className }) {
  let index = 0;
  return (
    <h1 className={className}>
      {parts.map((part, p) => {
        if (part === "\n") return <br key={`br-${p}`} />;
        const { text, accent } = typeof part === "string" ? { text: part } : part;
        const words = text.split(" ").filter(Boolean).map((word) => {
          const i = index++;
          return (
            <motion.span
              key={`${p}-${i}`}
              className={`headline-word${accent ? " accent-gradient" : ""}`}
              initial={{ opacity: 0, y: 28, filter: "blur(10px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ duration: 0.75, delay: 0.15 + i * 0.07, ease: EASE }}
            >
              {word}
            </motion.span>
          );
        });
        return accent ? <span key={`g-${p}`} style={{ whiteSpace: "nowrap" }}>{words}</span> : words;
      })}
    </h1>
  );
}

/** Stagger wrapper that wraps every child in a StaggerItem automatically (for grids of existing components). */
export function StaggerGrid({ children, className, style, inView = false, animateKey }) {
  const items = (Array.isArray(children) ? children.flat() : [children]).filter(Boolean);
  return (
    <Stagger className={className} style={style} inView={inView} animateKey={animateKey}>
      {items.map((child, i) => (
        <StaggerItem key={child.key ?? i}>{child}</StaggerItem>
      ))}
    </Stagger>
  );
}

/** Cross-fade + lift between tab panels. */
export function TabPanel({ id, children }) {
  return (
    <motion.div
      key={id}
      className="stack"
      style={{ "--gap": "20px" }}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
