import {
  createBrowserRouter,
  createMemoryRouter,
  Outlet,
  type RouteObject,
} from "react-router-dom";

import AppShell from "../components/layout/AppShell";
import { AuthProvider } from "../features/auth/AuthProvider";
import { ProtectedRoute, PublicOnlyRoute } from "../features/auth/AuthRoutes";
import LoginPage from "../features/auth/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import HoldingsPage from "../pages/HoldingsPage";
import ProfileSetupPage from "../pages/ProfileSetupPage";

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
          { path: "/", element: <DashboardPage /> },
          { path: "/profile/setup", element: <ProfileSetupPage /> },
          { path: "/holdings", element: <HoldingsPage /> },
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
