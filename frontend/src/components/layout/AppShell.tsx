import { BarChart3, ClipboardList, UserRound } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/holdings", label: "Holdings", icon: ClipboardList },
  { to: "/profile/setup", label: "Profile", icon: UserRound },
];

export default function AppShell() {
  return (
    <main className="app-frame">
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
              <item.icon aria-hidden="true" size={16} strokeWidth={1.8} />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="content-rail">
        <Outlet />
      </div>
    </main>
  );
}
