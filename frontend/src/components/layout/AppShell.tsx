import {
  ArrowLeftRight,
  Download,
  LayoutDashboard,
  Landmark,
  LogOut,
  UserRound,
  Monitor,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import AssistantWidget from "../../features/assistant/AssistantWidget";
import { useAuth } from "../../features/auth/AuthContext";
import { usePwaInstall } from "../../features/pwa/usePwaInstall";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/holdings",  label: "Holdings",  icon: Landmark },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/profile",   label: "Profile",   icon: UserRound },
];

const MODE_KEY = "portfolius:terminal-mode";

function readTerminalMode(): boolean {
  try {
    return localStorage.getItem(MODE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeTerminalMode(value: boolean) {
  try {
    localStorage.setItem(MODE_KEY, String(value));
  } catch {
    // Client-side presentation preference only; ignore unavailable storage.
  }
}

export default function AppShell() {
  const { user, signOut } = useAuth();
  const { canInstall, promptInstall } = usePwaInstall();
  const [isTerminal, setIsTerminal] = useState(readTerminalMode);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);

  // Mirror terminal mode onto the document root so native controls (scrollbars,
  // number spin buttons, select arrows) and the window scrollbar pick up the
  // dark color-scheme — color-scheme is inherited, so the root sets it for all.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("app-root--terminal", isTerminal);
    return () => {
      root.classList.remove("app-root--terminal");
    };
  }, [isTerminal]);

  // theme-color has no var() support, so read the page's own surface token
  // (index.css is already loaded by the time this runs) instead of
  // hard-coding a hex value that would drift from the design system.
  useEffect(() => {
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    if (!themeColorMeta) {
      return;
    }
    const surfaceVar = isTerminal ? "--ink-950" : "--paper-50";
    const surface = getComputedStyle(document.documentElement)
      .getPropertyValue(surfaceVar)
      .trim();
    if (surface) {
      themeColorMeta.setAttribute("content", surface);
    }
  }, [isTerminal]);

  function toggleMode() {
    setIsTerminal((prev) => {
      const next = !prev;
      writeTerminalMode(next);
      return next;
    });
  }

  async function handleSignOut() {
    setIsSigningOut(true);
    setSignOutError(null);
    try {
      await signOut();
    } catch {
      setSignOutError("Sign out failed. Try again.");
    } finally {
      setIsSigningOut(false);
    }
  }

  return (
    <main className={`app-frame${isTerminal ? " mode-terminal" : ""}`}>
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="wordmark">portfolius<span /></div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link--active" : "nav-link"
              }
            >
              <item.icon aria-hidden="true" size={16} strokeWidth={1.5} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {user?.email ? (
            <p className="sidebar-user" title={user.email}>
              {user.email}
            </p>
          ) : null}
          <button className="mode-toggle-btn" type="button" onClick={toggleMode}>
            {isTerminal
              ? <><Sun aria-hidden="true" size={16} strokeWidth={1.5} />Paper</>
              : <><Monitor aria-hidden="true" size={16} strokeWidth={1.5} />Terminal</>
            }
          </button>
          {canInstall ? (
            <button
              className="mode-toggle-btn"
              type="button"
              onClick={promptInstall}
            >
              <Download aria-hidden="true" size={16} strokeWidth={1.5} />
              Install
            </button>
          ) : null}
          <button
            className="mode-toggle-btn"
            disabled={isSigningOut}
            type="button"
            onClick={handleSignOut}
          >
            <LogOut aria-hidden="true" size={16} strokeWidth={1.5} />
            {isSigningOut ? "Signing out" : "Sign out"}
          </button>
          {signOutError ? (
            <p className="field-error" role="alert">
              {signOutError}
            </p>
          ) : null}
        </div>
      </aside>
      <div className="content-rail">
        <Outlet />
      </div>
      <AssistantWidget />
    </main>
  );
}
