import { useQuery } from "@tanstack/react-query";
import { Activity, CircleAlert, CircleCheck, Clock3 } from "lucide-react";
import { useMemo } from "react";

import { type BackendHealth, fetchBackendHealth } from "../lib/api";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function statusCopy(health: BackendHealth | undefined, isLoading: boolean) {
  if (isLoading) {
    return "Checking backend";
  }

  return health?.status === "ok" ? "Backend healthy" : "Backend unavailable";
}

function detailCopy(health: BackendHealth | undefined, isLoading: boolean) {
  if (isLoading) {
    return "Waiting for /healthz";
  }

  return health?.status === "ok"
    ? "GET /healthz returned ok"
    : health?.message ?? "Health check did not return a result";
}

function StatusIcon({
  health,
  isLoading,
}: {
  health: BackendHealth | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <Activity aria-hidden="true" className="health-icon health-icon--loading" />;
  }

  if (health?.status === "ok") {
    return <CircleCheck aria-hidden="true" className="health-icon health-icon--ok" />;
  }

  return <CircleAlert aria-hidden="true" className="health-icon health-icon--error" />;
}

export default function DashboardPage() {
  const healthQuery = useQuery({
    queryKey: ["backend-health", apiUrl],
    queryFn: () => fetchBackendHealth(apiUrl),
  });

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
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Portfolio overview</p>
          <h1 id="dashboard-title">Dashboard</h1>
        </div>
      </header>

      <div className="status-strip" aria-live="polite">
        <StatusIcon health={healthQuery.data} isLoading={healthQuery.isLoading} />
        <div>
          <p className="panel-label">Backend status</p>
          <strong>{statusCopy(healthQuery.data, healthQuery.isLoading)}</strong>
        </div>
        <span className="status-detail">{detailCopy(healthQuery.data, healthQuery.isLoading)}</span>
        <span className="status-endpoint num">{apiUrl.replace(/\/+$/, "")}/healthz</span>
        <span className="status-checked num">
          <Clock3 aria-hidden="true" />
          {checkedAt}
        </span>
      </div>
    </section>
  );
}
