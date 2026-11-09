const STATUS = {
  queued: { tone: "warn", label: "Queued" },
  preparing: { tone: "run", label: "Detecting players" },
  running: { tone: "run", label: "Analysing" },
  ready: { tone: "ok", label: "Ready" },
  completed: { tone: "ok", label: "Completed" },
  failed: { tone: "fail", label: "Failed" },
};

/** `error` lets a failed job caused by a server restart read as "Interrupted" instead of "Failed". */
export default function StatusBadge({ status, error }) {
  const interrupted = status === "failed" && /interrupted/i.test(String(error ?? ""));
  const { tone, label } = interrupted
    ? { tone: "warn", label: "Interrupted" }
    : STATUS[status] ?? { tone: "", label: status ? String(status) : "Unknown" };
  return (
    <span className={`badge ${tone}`} style={{ flex: "none" }}>
      <span className="dot" />
      {label}
    </span>
  );
}

export function isActive(status) {
  return ["queued", "preparing", "running"].includes(status);
}
