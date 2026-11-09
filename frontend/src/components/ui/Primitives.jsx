import { motion } from "motion/react";

import { CountUp, spotlightHandlers } from "../fx/Motion.jsx";

export function ProgressBar({ percent, indeterminate = false }) {
  return (
    <div className={`progress${indeterminate ? " indeterminate" : ""}`}>
      <div style={{ width: `${Math.max(2, Math.min(100, percent ?? 0))}%` }} />
    </div>
  );
}

export function Kpi({ icon: Icon, label, value, unit, note }) {
  return (
    <div className="kpi spotlight" {...spotlightHandlers()}>
      <div className="label">
        {Icon && <Icon size={13} />}
        {label}
      </div>
      <div className="value">
        <CountUp value={value} />
        {unit && <small>{unit}</small>}
      </div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="empty">
      {Icon && (
        <div className="icon">
          <Icon size={26} />
        </div>
      )}
      <h3 className="section-title">{title}</h3>
      <p className="muted" style={{ margin: "8px auto 20px", maxWidth: 440 }}>
        {children}
      </p>
      {action}
    </div>
  );
}

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

export function PageLoader({ label = "Loading..." }) {
  return (
    <div className="row muted" style={{ padding: 48, justifyContent: "center" }}>
      <Spinner /> {label}
    </div>
  );
}

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" />
      <span className="small">{label}</span>
    </label>
  );
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(({ id, label, icon: Icon }) => (
        <button key={id} role="tab" className={`tab${active === id ? " active" : ""}`} onClick={() => onChange(id)}>
          {Icon && <Icon size={16} />}
          {label}
          {active === id && <motion.span layoutId="tab-underline" className="tab-underline" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
        </button>
      ))}
    </div>
  );
}
