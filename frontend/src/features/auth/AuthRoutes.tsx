import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { TrendLoader } from "../../components/ui/TrendLoader";
import { useAuth } from "./AuthContext";

function AuthLoading() {
  return (
    <section className="page-section" aria-label="Loading authentication">
      <p className="eyebrow">Authentication</p>
      <h1>Checking session</h1>
      <TrendLoader label="Verifying your session" srLabel="Checking session" />
    </section>
  );
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoading, session } = useAuth();

  if (isLoading) {
    return <AuthLoading />;
  }

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { isLoading, session } = useAuth();

  if (isLoading) {
    return <AuthLoading />;
  }

  if (session) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
