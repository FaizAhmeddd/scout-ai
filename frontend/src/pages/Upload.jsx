import { AlertTriangle, CheckCircle2, FileVideo, Info, UploadCloud, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Topbar } from "../components/layout/AppShell.jsx";
import { ProgressBar } from "../components/ui/Primitives.jsx";
import { Notice } from "../components/ui/States.jsx";
import { videoApi } from "../services/api.js";
import { errorMessage, errorStatus, isCancelled } from "../services/apiClient.js";
import { duration } from "../utils/format.js";

// Mirrors backend ALLOWED_VIDEO_EXTENSIONS (app/storage/local_storage.py).
const EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".m4v"];
const ACCEPT = EXTENSIONS.join(",");
const MAX_BYTES = 4 * 1024 ** 3; // 4 GB - larger files are impractical to upload and process
const MAX_TITLE = 120;

function extensionOf(name = "") {
  const match = /\.[^.]+$/.exec(name);
  return match ? match[0].toLowerCase() : "";
}

function formatSize(bytes) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function validate(file) {
  if (!file) return "No file was selected.";
  const ext = extensionOf(file.name);
  if (!EXTENSIONS.includes(ext)) {
    return `"${file.name}" isn't a supported video format. Use MP4, MOV, AVI, MKV or M4V.`;
  }
  if (file.type && !file.type.startsWith("video/") && file.type !== "application/octet-stream") {
    return `"${file.name}" doesn't look like a video file (${file.type}).`;
  }
  if (file.size === 0) return "This file is empty. Choose a different video.";
  if (file.size > MAX_BYTES) return `This file is ${formatSize(file.size)}. Videos up to 4 GB are supported - trim the clip and try again.`;
  return null;
}

/** Reads duration/resolution in the browser to warn about clips that will give weak results (best effort). */
function useVideoMeta(file) {
  const [meta, setMeta] = useState(null);
  useEffect(() => {
    setMeta(null);
    if (!file) return undefined;
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    let done = false;
    const finish = (value) => {
      if (done) return;
      done = true;
      setMeta(value);
      URL.revokeObjectURL(url);
    };
    video.preload = "metadata";
    video.muted = true;
    video.onloadedmetadata = () =>
      finish({ duration: Number.isFinite(video.duration) ? video.duration : null, width: video.videoWidth, height: video.videoHeight });
    video.onerror = () => finish({ unreadable: true });
    const timer = setTimeout(() => finish({ unreadable: true }), 8000);
    video.src = url;
    return () => {
      clearTimeout(timer);
      done = true;
      URL.revokeObjectURL(url);
      video.removeAttribute("src");
    };
  }, [file]);
  return meta;
}

function uploadError(err) {
  const status = errorStatus(err);
  if (status === 415) return `${errorMessage(err)}. Use MP4, MOV, AVI, MKV or M4V.`;
  if (status === 422) return `${errorMessage(err)}. The file may be damaged or use an unusual codec - re-export it as an H.264 MP4 and try again.`;
  return errorMessage(err, "The upload failed. Please try again.");
}

export default function Upload() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const abortRef = useRef(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const meta = useVideoMeta(file);

  const uploading = progress !== null;

  // Warn before closing the tab mid-upload; abort the request if the user navigates away in-app.
  useEffect(() => {
    if (!uploading) return undefined;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [uploading]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const choose = (files) => {
    const selected = files?.[0];
    setInfo(null);
    if (!selected) return;
    const problem = validate(selected);
    if (problem) {
      setError(problem);
      return;
    }
    setFile(selected);
    setError(null);
    if (files.length > 1) setInfo(`${files.length} files were dropped - only "${selected.name}" will be uploaded.`);
    if (!title.trim()) setTitle(selected.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim().slice(0, MAX_TITLE));
  };

  const reset = () => {
    setFile(null);
    setTitle("");
    setError(null);
    setInfo(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const submit = async () => {
    if (uploading || !file || !title.trim()) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setError(null);
    setInfo(null);
    setProgress(0);
    try {
      const video = await videoApi.upload(file, title.trim(), setProgress, controller.signal);
      if (!video?.id) throw new Error("The server did not confirm the upload. Please check your library and try again.");
      navigate(`/app/videos/${video.id}`);
    } catch (err) {
      if (isCancelled(err)) setInfo("Upload cancelled. Your file was not saved.");
      else setError(uploadError(err));
      setProgress(null);
    } finally {
      abortRef.current = null;
    }
  };

  const cancel = () => abortRef.current?.abort();

  const warnings = [];
  if (meta && !meta.unreadable) {
    if (meta.duration != null && meta.duration < 10) warnings.push(`This clip is only ${Math.round(meta.duration)} s long - metrics need at least ~20 s of play to be reliable.`);
    if (meta.duration != null && meta.duration > 20 * 60) warnings.push(`This clip is ${duration(meta.duration)} long - processing will take a while. Clips under 10 minutes work best.`);
    if (meta.height && meta.height < 600) warnings.push(`Resolution is ${meta.width}×${meta.height}. 720p or higher gives much more accurate tracking.`);
  }

  return (
    <>
      <Topbar back="/app/library" crumbs={[{ label: "Video library", to: "/app/library" }, { label: "Upload" }]} />
      <div className="content">
        <div className="split wide">
          <div className="stack" style={{ "--gap": "20px", minWidth: 0 }}>
            <div>
              <h1 className="page-title">Upload a match video</h1>
              <p className="muted" style={{ marginTop: 4 }}>
                Detection of players, ball and pitch starts automatically as soon as the upload finishes.
              </p>
            </div>

            {!file ? (
              <>
                <div
                  className={`dropzone spotlight${drag ? " drag energy" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-label="Choose a video file to upload"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      inputRef.current?.click();
                    }
                  }}
                  onPointerMove={(e) => {
                    const r = e.currentTarget.getBoundingClientRect();
                    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
                    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
                  }}
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDrag(true);
                  }}
                  onDragLeave={() => setDrag(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDrag(false);
                    choose(e.dataTransfer.files);
                  }}
                >
                  <div className="icon float">
                    <UploadCloud size={30} />
                  </div>
                  <h3 className="section-title">Drop a video here, or click to browse</h3>
                  <p className="muted small" style={{ marginTop: 6 }}>MP4, MOV, AVI, MKV or M4V · up to 4 GB · broadcast or tactical camera</p>
                  <input ref={inputRef} type="file" accept={ACCEPT} hidden onChange={(e) => { choose(e.target.files); e.target.value = ""; }} />
                </div>
                {error && <div className="form-error row" role="alert" style={{ flexWrap: "nowrap" }}><AlertTriangle size={16} style={{ flex: "none" }} /> {error}</div>}
                {info && <Notice>{info}</Notice>}
              </>
            ) : (
              <div className={`card stack${uploading ? " energy" : ""}`}>
                <div className="spread" style={{ flexWrap: "nowrap" }}>
                  <div className="row" style={{ flexWrap: "nowrap", minWidth: 0 }}>
                    <div className="brand-mark" style={{ background: "var(--panel-2)", color: "var(--accent)", flex: "none" }}>
                      <FileVideo size={18} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div className="truncate" style={{ fontWeight: 700 }} title={file.name}>{file.name}</div>
                      <div className="tiny muted">
                        {formatSize(file.size)}
                        {meta && !meta.unreadable && meta.duration != null && ` · ${duration(meta.duration)}`}
                        {meta && !meta.unreadable && meta.height > 0 && ` · ${meta.width}×${meta.height}`}
                      </div>
                    </div>
                  </div>
                  {!uploading && (
                    <button className="btn ghost icon-btn" onClick={reset} title="Choose a different file" aria-label="Remove file">
                      <X size={16} />
                    </button>
                  )}
                </div>
                <div className="field">
                  <label htmlFor="title">Title</label>
                  <input id="title" className="input" value={title} disabled={uploading} maxLength={MAX_TITLE}
                    placeholder="e.g. VfB Stuttgart vs Bayer Leverkusen - 1st half" onChange={(e) => setTitle(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submit()} />
                  {!title.trim() && <span className="tiny" style={{ color: "var(--warn)" }}>Give the video a title to continue.</span>}
                </div>
                {!uploading && warnings.map((w) => (
                  <Notice key={w} tone="warn">{w}</Notice>
                ))}
                {uploading && (
                  <div className="stack" style={{ "--gap": "6px" }}>
                    <div className="spread small">
                      <span>{progress < 100 ? "Uploading... keep this tab open" : "Saving and checking the video..."}</span>
                      <span className="mono">{progress}%</span>
                    </div>
                    <ProgressBar percent={progress} indeterminate={progress === 100} />
                  </div>
                )}
                {error && <div className="form-error row" role="alert" style={{ flexWrap: "nowrap" }}><AlertTriangle size={16} style={{ flex: "none" }} /> {error}</div>}
                {info && <Notice icon={Info}>{info}</Notice>}
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  {uploading && progress < 100 && (
                    <button className="btn ghost" onClick={cancel}>
                      <X size={16} /> Cancel upload
                    </button>
                  )}
                  <button className="btn primary lg" disabled={uploading || !title.trim()} onClick={submit}>
                    <UploadCloud size={18} /> {uploading ? "Uploading..." : error ? "Try again" : "Upload & detect players"}
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="card stack">
            <h3 className="section-title">For the best results</h3>
            <ul className="tips" style={{ paddingLeft: 18, margin: 0 }}>
              <li>Wide broadcast or tactical camera with pitch lines visible</li>
              <li>720p or higher for the most accurate tracking</li>
              <li>Clips of 30 s - 10 min work best</li>
              <li>Fewer replays and close-ups means more measured time</li>
            </ul>
            <hr className="divider" />
            <h3 className="section-title">What happens next</h3>
            {[
              "Players, ball and pitch are tracked frame by frame",
              "Teams are identified from shirt colours",
              "You pick a team or click a player",
              "AI event analysis + tracking build the report",
            ].map((step) => (
              <div key={step} className="row small text-2" style={{ "--gap": "8px", flexWrap: "nowrap" }}>
                <CheckCircle2 size={16} color="var(--pitch)" style={{ flex: "none" }} /> {step}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
