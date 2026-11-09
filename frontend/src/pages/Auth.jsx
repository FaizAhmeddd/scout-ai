import { ArrowLeft, ArrowRight, Lock, Mail, User } from "lucide-react";
import { useState } from "react";
import { motion } from "motion/react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { Reveal, ScanFrame } from "../components/fx/Motion.jsx";
import { Notice } from "../components/ui/States.jsx";
import TrackingField from "../components/fx/TrackingField.jsx";

import Brand from "../components/layout/Brand.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { errorMessage } from "../services/apiClient.js";

function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="auth">
      <div className="auth-art">
        <TrackingField className="auth-field" showLabels={false} />
        <Brand />
        <Reveal className="stack" style={{ "--gap": "20px" }}>
          <div className="energy" style={{ borderRadius: 16 }}>
            <ScanFrame label="LIVE ANALYSIS">
              <img src="/showcase/annotated-frame.jpg" alt="Annotated match analysis" />
            </ScanFrame>
          </div>
          <div>
            <h2 style={{ fontSize: 24 }}>From broadcast footage to a scout's report.</h2>
            <p className="text-2" style={{ marginTop: 8 }}>
              Pose tracking, automatic pitch calibration and agentic AI event analysis - for a whole team or a
              single player.
            </p>
          </div>
        </Reveal>
        <span className="tiny muted">Pose tracking · Pitch calibration · Agentic video AI</span>
      </div>
      <div className="auth-form">
        <motion.div
          className="box stack"
          style={{ "--gap": "24px" }}
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Link to="/" className="back-link">
            <ArrowLeft size={16} /> Back to home
          </Link>
          <div>
            <h1 className="page-title">{title}</h1>
            <p className="muted" style={{ marginTop: 6 }}>{subtitle}</p>
          </div>
          {children}
          <p className="small muted" style={{ textAlign: "center" }}>{footer}</p>
        </motion.div>
      </div>
    </div>
  );
}

function Field({ icon: Icon, label, ...props }) {
  return (
    <div className="field">
      <label htmlFor={props.id}>{label}</label>
      <div className="input-icon">
        <Icon size={16} />
        <input className="input" {...props} />
      </div>
    </div>
  );
}

function safeRedirect(from) {
  return typeof from === "string" && from.startsWith("/app") ? from : "/app/library";
}

function useAuthSubmit(action) {
  const navigate = useNavigate();
  const location = useLocation();
  const { clearNotice } = useAuth();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event, payload) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    clearNotice();
    try {
      await action(payload);
      navigate(safeRedirect(location.state?.from), { replace: true });
    } catch (err) {
      const status = err?.response?.status;
      setError(
        status === 401 && !err?.response?.data?.detail
          ? "Incorrect email or password."
          : errorMessage(err, "Could not sign you in. Please try again.")
      );
      setBusy(false);
    }
  };
  return { submit, error, busy };
}

function SessionNotice() {
  const { notice } = useAuth();
  if (!notice) return null;
  return <Notice tone="warn" title="Signed out">{notice}</Notice>;
}

export function Login() {
  const { user, login } = useAuth();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const { submit, error, busy } = useAuthSubmit(login);
  if (user && !busy) return <Navigate to={safeRedirect(location.state?.from)} replace />;

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your analysis workspace."
      footer={<>No account yet? <Link to="/signup" style={{ color: "var(--accent)" }}>Create one</Link></>}
    >
      <form className="stack" onSubmit={(e) => submit(e, { ...form, email: form.email.trim() })}>
        <SessionNotice />
        {error && <div className="form-error" role="alert">{error}</div>}
        <Field id="email" icon={Mail} label="Email" type="email" autoComplete="email" required
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field id="password" icon={Lock} label="Password" type="password" autoComplete="current-password" required
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button className="btn primary lg" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"} <ArrowRight size={18} />
        </button>
      </form>
    </AuthLayout>
  );
}

export function Signup() {
  const { user, signup } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const { submit, error, busy } = useAuthSubmit(signup);
  if (user && !busy) return <Navigate to="/app/library" replace />;

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start analysing matches in under a minute."
      footer={<>Already have an account? <Link to="/login" style={{ color: "var(--accent)" }}>Sign in</Link></>}
    >
      <form className="stack" onSubmit={(e) => submit(e, { ...form, full_name: form.full_name.trim(), email: form.email.trim() })}>
        {error && <div className="form-error" role="alert">{error}</div>}
        <Field id="name" icon={User} label="Full name" autoComplete="name" required minLength={2} maxLength={80}
          value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <Field id="email" icon={Mail} label="Work email" type="email" autoComplete="email" required
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field id="password" icon={Lock} label="Password (min. 8 characters)" type="password" autoComplete="new-password"
          required minLength={8} maxLength={128} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button className="btn primary lg" disabled={busy}>
          {busy ? "Creating account..." : "Create account"} <ArrowRight size={18} />
        </button>
      </form>
    </AuthLayout>
  );
}
