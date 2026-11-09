import { AlertTriangle, ArrowLeft, Info, RefreshCw, SearchX, WifiOff } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage, isNotFound, isOffline } from "../../services/apiClient.js";

/** Friendly, designed replacement for a raw error: offline / server problem / generic, with a retry button. */
export function ErrorState({ error, title, onRetry, back, compact = false }) {
  const [retrying, setRetrying] = useState(false);
  const offline = isOffline(error);
  const Icon = offline ? WifiOff : AlertTriangle;
  const heading = title ?? (offline ? "Can't reach ScoutAI" : "Something went wrong");

  const retry = async () => {
    setRetrying(true);
    try {
      await onRetry?.();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className={`empty state-card${compact ? " compact" : ""}`} role="alert">
      <div className={`icon ${offline ? "tone-warn" : "tone-danger"}`}>
        <Icon size={26} />
      </div>
      <h3 className="section-title">{heading}</h3>
      <p className="muted" style={{ margin: "8px auto 20px", maxWidth: 460 }}>
        {errorMessage(error)}
      </p>
      <div className="row" style={{ justifyContent: "center" }}>
        {onRetry && (
          <button className="btn primary" onClick={retry} disabled={retrying}>
            <RefreshCw size={16} className={retrying ? "spin" : ""} /> {retrying ? "Retrying..." : "Try again"}
          </button>
        )}
        {back && (
          <Link className="btn" to={back.to}>
            <ArrowLeft size={16} /> {back.label}
          </Link>
        )}
      </div>
    </div>
  );
}

/** Shown for a deleted item or a bad id in the URL. */
export function NotFoundState({ title = "Not found", children, back }) {
  return (
    <div className="empty state-card">
      <div className="icon">
        <SearchX size={26} />
      </div>
      <h3 className="section-title">{title}</h3>
      <p className="muted" style={{ margin: "8px auto 20px", maxWidth: 460 }}>
        {children}
      </p>
      {back && (
        <Link className="btn primary" to={back.to}>
          <ArrowLeft size={16} /> {back.label}
        </Link>
      )}
    </div>
  );
}

/** Picks the right state for a failed load: not-found vs. retryable error. */
export function LoadError({ error, onRetry, notFoundTitle, notFoundText, back }) {
  if (isNotFound(error)) {
    return (
      <NotFoundState title={notFoundTitle} back={back}>
        {notFoundText}
      </NotFoundState>
    );
  }
  return <ErrorState error={error} onRetry={onRetry} back={back} />;
}

/** Inline banner. tone: info (neutral) | warn | danger | ok */
export function Notice({ tone = "info", icon: Icon = tone === "info" ? Info : AlertTriangle, title, children, action }) {
  return (
    <div className={`notice ${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon size={18} className="notice-icon" />
      <div className="notice-body">
        {title && <b>{title}</b>}
        {children && <div className="small text-2">{children}</div>}
      </div>
      {action && <div className="notice-action">{action}</div>}
    </div>
  );
}

/** Small banner for a lost connection while polling - existing data stays on screen. */
export function ConnectionBanner({ error }) {
  if (!error || !isOffline(error)) return null;
  return (
    <Notice tone="warn" icon={WifiOff} title="Connection lost - reconnecting...">
      Showing the last known status. This page refreshes automatically once the server is reachable again.
    </Notice>
  );
}

export function Skeleton({ width = "100%", height = 14, radius = 6, style }) {
  return <span className="skeleton" style={{ width, height, borderRadius: radius, ...style }} aria-hidden="true" />;
}

export function SkeletonKpis({ count = 3, min = "200px" }) {
  return (
    <div className="grid" style={{ "--min": min }} aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="kpi stack" style={{ "--gap": "10px" }}>
          <Skeleton width="45%" height={10} />
          <Skeleton width="60%" height={26} />
          <Skeleton width="70%" height={10} />
        </div>
      ))}
    </div>
  );
}

export function SkeletonCards({ count = 6, min = "290px", media = true }) {
  return (
    <div className="grid" style={{ "--min": min }} aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card flush">
          {media && <Skeleton height={0} radius={0} style={{ aspectRatio: "16 / 9", height: "auto", display: "block" }} />}
          <div className="stack" style={{ padding: 16, "--gap": "10px" }}>
            <Skeleton width="70%" height={16} />
            <Skeleton width="50%" height={10} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function SkeletonRows({ count = 4, min = "360px" }) {
  return (
    <div className="grid" style={{ "--min": min }} aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card row" style={{ flexWrap: "nowrap", "--gap": "14px" }}>
          <Skeleton width={56} height={72} radius={8} style={{ flex: "none" }} />
          <div className="stack" style={{ flex: 1, "--gap": "10px" }}>
            <Skeleton width="60%" height={14} />
            <Skeleton width="85%" height={10} />
            <Skeleton width="30%" height={10} />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Page-level skeleton: title block, KPI row and a large panel. */
export function SkeletonPage({ kpis = 4 }) {
  return (
    <div className="content stack" style={{ "--gap": "24px" }} aria-busy="true" aria-label="Loading">
      <div className="row" style={{ flexWrap: "nowrap", "--gap": "16px" }}>
        <Skeleton width={60} height={72} radius={10} style={{ flex: "none" }} />
        <div className="stack" style={{ flex: 1, "--gap": "10px" }}>
          <Skeleton width="40%" height={12} />
          <Skeleton width="55%" height={28} />
          <Skeleton width="30%" height={10} />
        </div>
      </div>
      <SkeletonKpis count={kpis} min="180px" />
      <div className="card">
        <Skeleton height={260} radius={10} />
      </div>
    </div>
  );
}
