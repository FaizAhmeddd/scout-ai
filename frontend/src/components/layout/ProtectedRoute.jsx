import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext.jsx";
import Brand from "./Brand.jsx";
import { PageLoader } from "../ui/Primitives.jsx";
import { ErrorState } from "../ui/States.jsx";

export default function ProtectedRoute() {
  const { user, loading, sessionError, retrySession, logout } = useAuth();
  const location = useLocation();
  if (loading) return <PageLoader label="Restoring your session..." />;
  if (!user && sessionError) {
    // Token kept: the server was unreachable, not the session invalid.
    return (
      <div className="container stack" style={{ paddingTop: 48, "--gap": "32px", maxWidth: 640 }}>
        <Brand />
        <ErrorState error={sessionError} title="Can't restore your session" onRetry={retrySession} />
        <button className="btn ghost sm" style={{ alignSelf: "center" }} onClick={logout}>
          Sign in with a different account
        </button>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  return <Outlet />;
}
