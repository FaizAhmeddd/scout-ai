import { ArrowLeft, BookOpen, Film, LayoutGrid, LogOut, Upload } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { NavLink, useLocation, useNavigate, useOutlet } from "react-router-dom";

import { useAuth } from "../../context/AuthContext.jsx";
import { initials } from "../../utils/format.js";
import ErrorBoundary from "../ui/ErrorBoundary.jsx";
import Brand from "./Brand.jsx";

const NAV = [
  { to: "/app/library", label: "Video library", icon: LayoutGrid },
  { to: "/app/upload", label: "Upload & analyse", icon: Upload },
  { to: "/app/analyses", label: "All analyses", icon: Film },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const outlet = useOutlet();

  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand to="/app/library" />
        <div>
          <div className="nav-label">Workspace</div>
          <nav className="nav">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} aria-label={label} title={label}>
                <Icon size={18} />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div>
          <div className="nav-label">Product</div>
          <nav className="nav">
            <NavLink to="/" end aria-label="How it works" title="How it works">
              <BookOpen size={18} />
              How it works
            </NavLink>
          </nav>
        </div>
        <div className="user-chip">
          <div className="avatar">{initials(user?.full_name)}</div>
          <div className="who" style={{ minWidth: 0, flex: 1 }}>
            <div className="small truncate" style={{ fontWeight: 700 }}>
              {user?.full_name || "Your account"}
            </div>
            <div className="tiny muted truncate">
              {user?.email}
            </div>
          </div>
          <button
            className="btn ghost icon-btn"
            title="Sign out"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main className="main">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            className="page"
            initial={{ opacity: 0, y: 14, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            <ErrorBoundary resetKey={location.pathname}>{outlet}</ErrorBoundary>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export function BackButton({ fallback }) {
  const navigate = useNavigate();
  // React Router records the history index; idx 0 means the page was opened directly (no in-app history).
  const canGoBack = (window.history.state?.idx ?? 0) > 0;
  return (
    <button className="btn ghost sm" onClick={() => (canGoBack ? navigate(-1) : navigate(fallback))} title="Go back">
      <ArrowLeft size={16} /> Back
    </button>
  );
}

export function Topbar({ crumbs = [], actions, back }) {
  return (
    <header className="topbar">
      <div className="crumbs">
        {back && <BackButton fallback={back} />}
        {back && <span className="topbar-sep" />}
        {crumbs.map((crumb, i) => (
          <span key={`${i}-${crumb.label}`} className="row" style={{ "--gap": "8px" }}>
            {i > 0 && <span>/</span>}
            {crumb.to ? (
              <NavLink to={crumb.to} title={crumb.label || undefined}>{crumb.label || "..."}</NavLink>
            ) : (
              <span className="current" title={crumb.label || undefined}>{crumb.label || "..."}</span>
            )}
          </span>
        ))}
      </div>
      <div className="row">{actions}</div>
    </header>
  );
}
