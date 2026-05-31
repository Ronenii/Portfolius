import { useEffect, useMemo, useState } from "react";

import { type BackendHealth, fetchBackendHealth } from "./lib/api";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type HealthState =
  | { kind: "loading" }
  | { kind: "ready"; health: BackendHealth };

function StatusMark({ state }: { state: HealthState }) {
  if (state.kind === "loading") {
    return <span className="status-mark status-mark--loading" aria-hidden="true" />;
  }

  return (
    <span
      className={
        state.health.status === "ok"
          ? "status-mark status-mark--ok"
          : "status-mark status-mark--error"
      }
      aria-hidden="true"
    />
  );
}

function statusCopy(state: HealthState): string {
  if (state.kind === "loading") {
    return "Checking backend";
  }

  return state.health.status === "ok" ? "Backend healthy" : "Backend unavailable";
}

function detailCopy(state: HealthState): string {
  if (state.kind === "loading") {
    return "Waiting for /healthz";
  }

  return state.health.status === "ok"
    ? "GET /healthz returned ok"
    : state.health.message;
}

export default function App() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let isMounted = true;

    fetchBackendHealth(apiUrl).then((health) => {
      if (isMounted) {
        setState({ kind: "ready", health });
      }
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const checkedAt = useMemo(
    () =>
      new Intl.DateTimeFormat("en", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date()),
    []
  );

  return (
    <main className="app-shell min-h-screen">
      <section className="hero-panel" aria-labelledby="page-title">
        <div className="brand-row">
          <div className="wordmark">portfolius<span /></div>
          <span className="badge">M0 walking skeleton</span>
        </div>

        <div className="hero-grid">
          <div className="intro-copy">
            <p className="eyebrow">Frontend health check</p>
            <h1 id="page-title">Long-term investor dashboard.</h1>
            <p className="lede">
              The browser can load the Vite app and ask FastAPI whether the
              backend is alive.
            </p>
          </div>

          <aside className="health-panel" aria-live="polite">
            <div className="health-heading">
              <StatusMark state={state} />
              <div>
                <p className="panel-label">Backend status</p>
                <h2>{statusCopy(state)}</h2>
              </div>
            </div>

            <dl className="status-list">
              <div>
                <dt>Endpoint</dt>
                <dd className="num">{apiUrl.replace(/\/+$/, "")}/healthz</dd>
              </div>
              <div>
                <dt>Result</dt>
                <dd>{detailCopy(state)}</dd>
              </div>
              <div>
                <dt>Checked</dt>
                <dd className="num">{checkedAt}</dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>
    </main>
  );
}
