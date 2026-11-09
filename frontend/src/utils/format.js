/** True for a real, finite number (rejects null, undefined, NaN, Infinity and non-numeric strings). */
export function isNum(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

export function duration(seconds) {
  if (!isNum(seconds) || seconds < 0) return "-";
  const total = Math.round(Number(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function relativeTime(iso) {
  if (!iso) return "";
  const time = new Date(iso).getTime();
  if (!Number.isFinite(time)) return "";
  const diff = (Date.now() - time) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function num(value, digits = 0, suffix = "") {
  if (!isNum(value)) return "-";
  return `${Number(value).toFixed(digits)}${suffix}`;
}

/** Number with a unit, or "-" (no dangling unit) when the value is missing. */
export function unit(value, suffix, digits = 0) {
  return isNum(value) ? `${Number(value).toFixed(digits)} ${suffix}` : "-";
}

/** Integer count, "-" when missing. */
export function count(value) {
  return isNum(value) ? String(Math.round(Number(value))) : "-";
}

export function pct(part, whole) {
  return isNum(part) && isNum(whole) && Number(whole) > 0 ? `${Math.round((part / whole) * 100)}%` : "-";
}

/** 0-1 share as a percentage. */
export function share(value, digits = 0) {
  return isNum(value) ? `${(Number(value) * 100).toFixed(digits)}%` : "-";
}

export function ratio(part, whole) {
  return `${isNum(part) ? part : 0}/${isNum(whole) ? whole : 0}`;
}

export function initials(name = "") {
  return String(name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

export function titleCase(text = "") {
  return String(text ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Safe array access for report fields that may be missing or the wrong type. */
export function list(value) {
  return Array.isArray(value) ? value : [];
}

/** Safe object access for report fields that may be missing or the wrong type. */
export function obj(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

/** User-facing status of the AI event analysis (never exposes provider or model details). */
export function aiStatus(status) {
  const s = String(status ?? "");
  if (s.startsWith("ok")) return "complete";
  if (s === "disabled") return "off";
  if (s === "no API key") return "not configured";
  return "unavailable";
}

/** Neutral explanation of why AI-detected events are missing from a report. */
export function aiStatusNotice(status) {
  switch (aiStatus(status)) {
    case "off":
      return "AI event analysis was switched off for this run, so passes, dribbles, shots and duels were not counted.";
    case "not configured":
      return "AI event analysis is not configured on this ScoutAI server, so passes, dribbles, shots and duels were not counted.";
    case "complete":
      return "The AI analyst did not return any events for this target.";
    default:
      return "AI event analysis could not complete for this run, so passes, dribbles, shots and duels were not counted.";
  }
}

const VENDOR_TERMS = [
  [/\b(google\s+)?gemini(?:[\s-]+(?:\d[\w.]*|flash|pro|ultra|nano|lite|preview|exp))*\b/gi, "the AI analyst"],
  [/\bgoogle(\s+genai)?\b/gi, "the AI service"],
  [/\b(ultralytics|yolo\w*|rf-?detr|bytetrack|botsort|tracktrack|sam2?|siglip|roboflow|openai)\b/gi, "the model"],
  [/\b(cuda|cudnn|nvidia|gpu|vram|laptop)\b/gi, "server"],
];

/** Removes vendor, model and hardware names from text produced by the server or the AI analyst. */
export function cleanText(text) {
  if (text === null || text === undefined) return "";
  let out = String(text);
  for (const [pattern, replacement] of VENDOR_TERMS) out = out.replace(pattern, replacement);
  return out;
}

/** Turns a raw job error into a friendly title + guidance, hiding internal details. */
export function jobError(error, kind = "analysis") {
  const raw = String(error ?? "");
  if (/interrupted/i.test(raw)) {
    return {
      interrupted: true,
      title: "Interrupted by a server restart",
      message:
        kind === "video"
          ? "The ScoutAI server restarted while players were being detected. Retry detection to pick up where it left off - nothing was lost."
          : "The ScoutAI server restarted while this analysis was running. Run it again - tracking is cached, so it will be faster.",
    };
  }
  if (/out of memory|cuda|gpu|vram|memory/i.test(raw)) {
    return {
      title: "The server ran out of processing capacity",
      message: "This job needed more resources than were available at the time. Try again in a moment, or use a shorter clip.",
    };
  }
  if (/could not be read|no readable frames|codec|decode/i.test(raw)) {
    return {
      title: "The video could not be read",
      message: "The file looks damaged or uses an unsupported codec. Re-export it as an H.264 MP4 and upload it again.",
    };
  }
  if (/no players|no teams|not enough|too few/i.test(raw)) {
    return {
      title: kind === "video" ? "Not enough players were found" : "Not enough tracking data",
      message: `${cleanText(raw).replace(/\.\s*$/, "")}. Wide broadcast footage with the pitch visible works best.`,
    };
  }
  return {
    title: kind === "video" ? "Player detection failed" : "The analysis failed",
    message: raw ? cleanText(raw) : "Something went wrong while processing. Please try again.",
  };
}
