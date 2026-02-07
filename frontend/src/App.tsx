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
      <aside className="w-64 border-r border-border bg-[#12121a] flex flex-col">
        <div className="p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-violet-500">
              <Radar className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">Hunter</h1>
              <p className="text-[11px] text-muted-foreground leading-none">Job Search Automation</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200 ${
                  isActive
                    ? "bg-indigo-dim text-primary font-medium"
                    : "text-[#8888a0] hover:bg-white/[0.04] hover:text-foreground"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {connected ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
                </span>
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
