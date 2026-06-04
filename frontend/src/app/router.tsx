import {
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from "react-router-dom";

import AppShell from "../components/layout/AppShell";
import DashboardPage from "../pages/DashboardPage";
import HoldingsPage from "../pages/HoldingsPage";
import LoginPage from "../pages/LoginPage";
import ProfileSetupPage from "../pages/ProfileSetupPage";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/profile/setup", element: <ProfileSetupPage /> },
      { path: "/holdings", element: <HoldingsPage /> },
    ],
  },
];

export function createAppRouter(initialEntries?: string[]) {
  if (initialEntries) {
    return createMemoryRouter(routes, { initialEntries });
  }

  return createBrowserRouter(routes);
}
