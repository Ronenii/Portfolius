import { LayoutDashboard, Landmark, UserRound, Monitor, Sun } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import AssistantWidget from "../../features/assistant/AssistantWidget";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/holdings",  label: "Holdings",  icon: Landmark },
  { to: "/profile",   label: "Profile",   icon: UserRound },
];

const MODE_KEY = "portfolius:terminal-mode";

export default function AppShell() {
  const [isTerminal, setIsTerminal] = useState(
    () => localStorage.getItem(MODE_KEY) === "true"
  );

  function toggleMode() {
    setIsTerminal((prev) => {
      const next = !prev;
      localStorage.setItem(MODE_KEY, String(next));
      return next;
    });
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
          <button className="mode-toggle-btn" type="button" onClick={toggleMode}>
            {isTerminal
              ? <><Sun aria-hidden="true" size={16} strokeWidth={1.5} />Paper</>
              : <><Monitor aria-hidden="true" size={16} strokeWidth={1.5} />Terminal</>
            }
          </button>
        </div>
      </aside>
      <div className="content-rail">
        <Outlet />
      </div>
      <AssistantWidget />
    </main>
  );
}
