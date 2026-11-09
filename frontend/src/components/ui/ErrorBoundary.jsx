import { AlertTriangle, Home, RefreshCw } from "lucide-react";
import { Component } from "react";

/**
 * Catches render errors so a single broken view never blanks the whole app.
 * Pass `resetKey` (e.g. the route path) to clear the error when the user navigates elsewhere.
 */
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("ScoutAI view crashed:", error, info?.componentStack);
  }

  componentDidUpdate(prevProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    const fullPage = this.props.fullPage;
    return (
      <div className={fullPage ? "container" : "content"} style={fullPage ? { paddingTop: 80 } : undefined}>
        <div className="empty state-card" role="alert">
          <div className="icon tone-danger">
            <AlertTriangle size={26} />
          </div>
          <h3 className="section-title">This view hit a snag</h3>
          <p className="muted" style={{ margin: "8px auto 20px", maxWidth: 460 }}>
            Something unexpected happened while showing this page. Your data is safe - reload the page or head back to
            your library.
          </p>
          <div className="row" style={{ justifyContent: "center" }}>
            <button className="btn primary" onClick={() => window.location.reload()}>
              <RefreshCw size={16} /> Reload page
            </button>
            <a className="btn" href="/app/library">
              <Home size={16} /> Video library
            </a>
          </div>
        </div>
      </div>
    );
  }
}
