import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext";

function AuthLoading() {
  return (
    <section className="page-section" aria-label="Loading authentication">
      <p className="eyebrow">Authentication</p>
      <h1>Checking session</h1>
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
    return <Navigate to="/" replace />;
  }

  return children;
}
