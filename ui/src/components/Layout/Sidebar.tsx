import { NavLink } from "react-router-dom";
import { useRunStatus } from "@/api/run";

const links = [
  { to: "/",         label: "Dashboard",  icon: "⬡" },
  { to: "/profiles", label: "Profiles",   icon: "⚙" },
  { to: "/run",      label: "Run",        icon: "▶" },
  { to: "/pricing",  label: "Pricing",    icon: "$" },
  { to: "/config",   label: "Config",     icon: "✎" },
];

export default function Sidebar() {
  const { data: status } = useRunStatus();
  const running = status?.status === "running";

  return (
    <aside className="w-52 bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-gray-800">
        <span className="text-sm font-bold tracking-widest text-blue-400 uppercase">
          Agent Sim
        </span>
      </div>

      {/* Run status pill */}
      <div className="px-5 py-3 border-b border-gray-800">
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
            running
              ? "bg-green-900 text-green-300"
              : "bg-gray-800 text-gray-400"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              running ? "bg-green-400 animate-pulse" : "bg-gray-500"
            }`}
          />
          {running ? "Running" : "Idle"}
        </span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
              }`
            }
          >
            <span className="text-base leading-none">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* External links */}
      <div className="px-5 py-4 border-t border-gray-800 space-y-1">
        <p className="text-xs text-gray-600 mb-2 uppercase tracking-wider">Dashboards</p>
        {[
          { href: "http://localhost:16686", label: "Jaeger" },
          { href: "http://localhost:3000",  label: "Grafana" },
          { href: "http://localhost:9090",  label: "Prometheus" },
        ].map(({ href, label }) => (
          <a
            key={href}
            href={href}
            target="_blank"
            rel="noreferrer"
            className="block text-xs text-gray-500 hover:text-blue-400 transition-colors"
          >
            ↗ {label}
          </a>
        ))}
      </div>
    </aside>
  );
}
