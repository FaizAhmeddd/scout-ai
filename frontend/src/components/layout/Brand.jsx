import { Activity } from "lucide-react";
import { Link } from "react-router-dom";

export const PRODUCT_NAME = "ScoutAI";

export default function Brand({ to = "/" }) {
  return (
    <Link to={to} className="brand" aria-label={PRODUCT_NAME}>
      <span className="brand-mark">
        <Activity size={18} strokeWidth={2.6} />
      </span>
      <span>
        Scout<span style={{ color: "var(--accent)" }}>AI</span>
      </span>
    </Link>
  );
}
