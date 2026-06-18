import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { TrendLoader } from "../../components/ui/TrendLoader";
import { useAuth } from "./AuthContext";

function AuthLoading() {
  return (
    <div className="loading-screen" aria-label="Loading authentication">
      <TrendLoader label="Verifying your session" srLabel="Checking session" />
    </div>
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
