import { Film, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import AnalysisCard from "../components/analysis/AnalysisCard.jsx";
import { Stagger, StaggerItem } from "../components/fx/Motion.jsx";
import { Topbar } from "../components/layout/AppShell.jsx";
import { EmptyState } from "../components/ui/Primitives.jsx";
import { ConnectionBanner, ErrorState, SkeletonRows } from "../components/ui/States.jsx";
import { isActive } from "../components/ui/StatusBadge.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { analysisApi } from "../services/api.js";
import { list } from "../utils/format.js";

export default function Analyses() {
  const { data, error, retry } = usePolling(analysisApi.recent, {
    shouldPoll: (items) => list(items).some((a) => isActive(a.status)),
  });
  const analyses = data ? list(data) : null;

  return (
    <>
      <Topbar back="/app/library" crumbs={[{ label: "All analyses" }]} />
      <div className="content stack" style={{ "--gap": "20px" }}>
        <div>
          <h1 className="page-title">All analyses</h1>
          <p className="muted" style={{ marginTop: 4 }}>Every team and player report across your videos, newest first.</p>
        </div>
        {analyses && <ConnectionBanner error={error} />}
        {!analyses && error && <ErrorState error={error} title="Couldn't load your analyses" onRetry={retry} />}
        {!analyses && !error && <SkeletonRows count={6} min="380px" />}
        {analyses?.length === 0 && (
          <EmptyState icon={Film} title="No analyses yet" action={<Link className="btn primary" to="/app/library"><Plus size={16} /> Choose a video</Link>}>
            Open a video from your library, then pick a team or a player to generate the first report.
          </EmptyState>
        )}
        {analyses?.length > 0 && (
          <Stagger className="grid" style={{ "--min": "380px" }} inView={false} animateKey={analyses.length}>
            {analyses.map((a) => (
              <StaggerItem key={a.id}>
                <AnalysisCard analysis={a} showVideo onDeleted={retry} />
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </div>
    </>
  );
}
