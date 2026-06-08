import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  Outlet,
  type RouteObject,
} from "react-router-dom";

import AppShell from "../components/layout/AppShell";
import { AuthProvider } from "../features/auth/AuthProvider";
import { ProtectedRoute, PublicOnlyRoute } from "../features/auth/AuthRoutes";
import LoginPage from "../features/auth/LoginPage";
import HoldingsPage from "../features/holdings/HoldingsPage";
import ProfileEditPage from "../features/profile/ProfileEditPage";
import ProfileGate from "../features/profile/ProfileGate";
import ProfileWizardPage from "../features/profile/ProfileWizardPage";
import DashboardPage from "../pages/DashboardPage";

export const routes: RouteObject[] = [
  {
    element: (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    ),
    children: [
      {
        path: "/login",
        element: (
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        ),
      },
      {
        element: (
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        ),
        children: [
          {
            element: <ProfileGate />,
            children: [
              { index: true, element: <Navigate to="/dashboard" replace /> },
              { path: "/dashboard", element: <DashboardPage /> },
              { path: "/profile/setup", element: <ProfileWizardPage /> },
              { path: "/profile", element: <ProfileEditPage /> },
              { path: "/holdings", element: <HoldingsPage /> },
            ],
          },
        ],
      },
    ],
  },
];

export function createAppRouter(initialEntries?: string[]) {
  if (initialEntries) {
    return createMemoryRouter(routes, { initialEntries });
  }

  return createBrowserRouter(routes);
}
