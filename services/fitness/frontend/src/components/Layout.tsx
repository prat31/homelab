import { NavLink, Outlet } from "react-router-dom";

const links = [
  ["/", "Overview"],
  ["/activity", "Activity"],
  ["/workouts", "Workouts"],
  ["/sleep", "Sleep"],
  ["/body", "Body"],
  ["/data", "Data"],
];

export function Layout() {
  return (
    <div className="layout">
      <nav className="nav">
        <h1>Fitness</h1>
        {links.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
            {label}
          </NavLink>
        ))}
      </nav>
      <main className="page">
        <Outlet />
      </main>
    </div>
  );
}
