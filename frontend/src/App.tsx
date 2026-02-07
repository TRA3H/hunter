import { useCallback, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import {
  BarChart3,
  BriefcaseBusiness,
  FileText,
  LayoutDashboard,
  Radar,
  Settings,
  Send,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { WSEvent } from "@/types";

import DashboardPage from "@/pages/DashboardPage";
import BoardsPage from "@/pages/BoardsPage";
import JobsPage from "@/pages/JobsPage";
import AutoApplyPage from "@/pages/AutoApplyPage";
import ProfilePage from "@/pages/ProfilePage";
import SettingsPage from "@/pages/SettingsPage";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/boards", icon: Radar, label: "Boards" },
  { to: "/jobs", icon: BriefcaseBusiness, label: "Jobs" },
  { to: "/autoapply", icon: Send, label: "Auto-Apply" },
  { to: "/profile", icon: FileText, label: "Profile" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function App() {
  const [notifications, setNotifications] = useState<WSEvent[]>([]);

  const handleWSEvent = useCallback((event: WSEvent) => {
    setNotifications((prev) => [event, ...prev].slice(0, 50));
  }, []);

  const { connected } = useWebSocket(handleWSEvent);

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-card flex flex-col">
        <div className="p-6">
          <h1 className="text-xl font-bold tracking-tight">Hunter</h1>
          <p className="text-xs text-muted-foreground mt-1">Job Search Automation</p>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {connected ? (
              <>
                <Wifi className="h-3 w-3 text-green-500" />
                <span>Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="h-3 w-3 text-red-500" />
                <span>Disconnected</span>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<DashboardPage notifications={notifications} />} />
          <Route path="/boards" element={<BoardsPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/autoapply" element={<AutoApplyPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
