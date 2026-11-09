import { ArrowLeft, Compass, Home } from "lucide-react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import AppShell, { Topbar } from "./components/layout/AppShell.jsx";
import Brand from "./components/layout/Brand.jsx";
import ProtectedRoute from "./components/layout/ProtectedRoute.jsx";
import { EmptyState } from "./components/ui/Primitives.jsx";
import AnalysisDetail from "./pages/AnalysisDetail.jsx";
import Analyses from "./pages/Analyses.jsx";
import { Login, Signup } from "./pages/Auth.jsx";
import Landing from "./pages/Landing.jsx";
import Library from "./pages/Library.jsx";
import Upload from "./pages/Upload.jsx";
import VideoDetail from "./pages/VideoDetail.jsx";

function NotFound() {
  return (
    <div className="container stack" style={{ paddingTop: 32, "--gap": "48px" }}>
      <div className="public-nav"><Brand /></div>
      <EmptyState
        icon={Compass}
        title="Page not found"
        action={
          <div className="row" style={{ justifyContent: "center" }}>
            <Link className="btn primary" to="/app/library"><Home size={16} /> Open your library</Link>
            <Link className="btn" to="/"><ArrowLeft size={16} /> Home</Link>
          </div>
        }
      >
        This page doesn't exist - the link may be mistyped or out of date.
      </EmptyState>
    </div>
  );
}

function AppNotFound() {
  return (
    <>
      <Topbar back="/app/library" crumbs={[{ label: "Not found" }]} />
      <div className="content">
        <EmptyState
          icon={Compass}
          title="Page not found"
          action={<Link className="btn primary" to="/app/library"><ArrowLeft size={16} /> Back to your library</Link>}
        >
          This page doesn't exist in your workspace. It may have been moved or the link is out of date.
        </EmptyState>
      </div>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Navigate to="library" replace />} />
          <Route path="library" element={<Library />} />
          <Route path="upload" element={<Upload />} />
          <Route path="analyses" element={<Analyses />} />
          <Route path="videos/:videoId" element={<VideoDetail />} />
          <Route path="analyses/:analysisId" element={<AnalysisDetail />} />
          <Route path="*" element={<AppNotFound />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
