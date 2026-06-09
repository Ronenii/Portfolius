import { useQuery } from "@tanstack/react-query";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { TrendLoader } from "../../components/ui/TrendLoader";
import { ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { getProfile } from "./profile-api";

function ProfileLoading() {
  return (
    <section className="page-section" aria-label="Loading profile">
      <p className="eyebrow">Profile</p>
      <TrendLoader label="Loading your profile" srLabel="Loading profile" />
    </section>
  );
}

function ProfileError() {
  return (
    <section className="page-section" aria-labelledby="profile-error-title">
      <p className="eyebrow">Profile</p>
      <h1 id="profile-error-title">Profile unavailable</h1>
      <p className="status-detail">
        We could not load your profile. Refresh the page or try again shortly.
      </p>
    </section>
  );
}

export default function ProfileGate() {
  const { accessToken } = useAuth();
  const location = useLocation();

  const profileQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["profile", accessToken],
    queryFn: () => getProfile(accessToken ?? ""),
    retry: false,
  });

  if (!accessToken || profileQuery.isLoading) {
    return <ProfileLoading />;
  }

  const isSetupRoute = location.pathname === "/profile/setup";
  const isMissingProfile =
    profileQuery.error instanceof ApiError && profileQuery.error.status === 404;

  if (isMissingProfile) {
    return isSetupRoute ? <Outlet /> : <Navigate to="/profile/setup" replace />;
  }

  if (profileQuery.error) {
    return <ProfileError />;
  }

  if (isSetupRoute || location.pathname === "/") {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
