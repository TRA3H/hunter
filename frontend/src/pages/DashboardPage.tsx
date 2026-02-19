import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  ClipboardList,
  Radar,
  TrendingUp,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import MatchScoreDot from "@/components/MatchScoreDot";
import { formatRelativeTime } from "@/lib/utils";
import { applicationsApi } from "@/lib/api";
import type { DashboardStats, WSEvent } from "@/types";

interface DashboardPageProps {
  notifications: WSEvent[];
}

function DashboardPage({ notifications }: DashboardPageProps) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchDashboard() {
      try {
        setLoading(true);
        setError(null);
        const data = await applicationsApi.dashboard();
        if (!cancelled) {
          setStats(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchDashboard();

    return () => {
      cancelled = true;
    };
  }, []);

  // Re-fetch when relevant WebSocket events arrive
  useEffect(() => {
    if (notifications.length === 0) return;

    const latest = notifications[notifications.length - 1];
    const refreshTypes = [
      "scan_complete",
      "application_update",
      "application_submitted",
      "job_discovered",
    ];

    if (refreshTypes.includes(latest.type)) {
      applicationsApi.dashboard().then(setStats).catch(() => {});
    }
  }, [notifications]);

  // Extract recent jobs from notifications for the feed
  const recentJobs = notifications
    .filter((n) => n.type === "job_discovered" || n.type === "scan_complete")
    .slice(-10)
    .reverse()
    .map((n) => ({
      title: (n.data.title as string) || "New Job",
      company: (n.data.company as string) || "Unknown",
      matchScore: (n.data.match_score as number) || 0,
      boardName: (n.data.board_name as string) || "",
      timestamp: (n.data.timestamp as string) || new Date().toISOString(),
    }));

  const isConnected = notifications.length > 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-3">
          <Radar className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card className="max-w-md w-full">
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{error}</p>
            <button
              onClick={() => {
                setLoading(true);
                setError(null);
                applicationsApi
                  .dashboard()
                  .then(setStats)
                  .catch((err) =>
                    setError(err instanceof Error ? err.message : "Failed to load dashboard")
                  )
                  .finally(() => setLoading(false));
              }}
              className="mt-4 text-sm text-primary hover:underline"
            >
              Try again
            </button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!stats) return null;

  const statCards = [
    {
      title: "Active Boards",
      value: stats.active_boards,
      icon: Radar,
      color: "text-violet-500",
      bgColor: "bg-violet-500/10",
    },
    {
      title: "New Jobs",
      value: stats.new_jobs,
      icon: BriefcaseBusiness,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
    },
    {
      title: "Applications",
      value: stats.total_applications,
      icon: ClipboardList,
      color: "text-amber-500",
      bgColor: "bg-amber-500/10",
    },
    {
      title: "Interviewing",
      value: stats.applications_by_status?.interviewing ?? 0,
      icon: TrendingUp,
      color: "text-green-500",
      bgColor: "bg-green-500/10",
    },
  ];

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {stats.total_jobs} jobs tracked across {stats.active_boards} boards
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              isConnected ? "bg-green-500 animate-pulse" : "bg-muted-foreground"
            }`}
          />
          <span className="text-xs text-muted-foreground">
            {isConnected ? "Live" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
          <Card key={card.title} className={`animate-fade-up animation-delay-${(i + 1) * 100}`}>
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.title}
              </CardTitle>
              <div className={`p-2 rounded-lg ${card.bgColor}`}>
                <card.icon className={`h-4 w-4 ${card.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-serif">{card.value}</div>
              {card.title === "New Jobs" && stats.total_jobs > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  of {stats.total_jobs} total
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Jobs by Board */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              Jobs by Board
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats.jobs_by_board.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={stats.jobs_by_board}
                  margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                  <XAxis
                    dataKey="board"
                    tick={{ fontSize: 12, fill: "#8888a0" }}
                    axisLine={{ stroke: "#2a2a3a" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: "#8888a0" }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1c1c28",
                      border: "1px solid #2a2a3a",
                      borderRadius: "8px",
                      color: "#e8e8f0",
                      fontSize: 13,
                    }}
                  />
                  <Bar
                    dataKey="count"
                    fill="#6366f1"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={48}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[260px] text-sm text-muted-foreground">
                No board data available yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* Applications Over Time */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              Applications Over Time
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats.applications_over_time.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart
                  data={stats.applications_over_time}
                  margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12, fill: "#8888a0" }}
                    axisLine={{ stroke: "#2a2a3a" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: "#8888a0" }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1c1c28",
                      border: "1px solid #2a2a3a",
                      borderRadius: "8px",
                      color: "#e8e8f0",
                      fontSize: 13,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fill="url(#areaGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[260px] text-sm text-muted-foreground">
                No application data available yet
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row: Recent Jobs + Activity Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Jobs Feed */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BriefcaseBusiness className="h-4 w-4 text-muted-foreground" />
              Recent Jobs
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentJobs.length > 0 ? (
              <div className="space-y-3">
                {recentJobs.map((job, idx) => (
                  <div
                    key={`${job.title}-${job.company}-${idx}`}
                    className="flex items-start justify-between gap-3 py-2 border-b border-border last:border-0"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{job.title}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {job.company}
                        {job.boardName && (
                          <span className="ml-1.5 text-muted-foreground/60">
                            via {job.boardName}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {job.matchScore > 0 && (
                        <MatchScoreDot score={job.matchScore} size="sm" />
                      )}
                      <span className="text-[11px] text-muted-foreground whitespace-nowrap">
                        {formatRelativeTime(job.timestamp)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <BriefcaseBusiness className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">No recent jobs discovered</p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Jobs will appear here as boards are scanned
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Activity Log */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-muted-foreground" />
              Activity Log
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats.recent_activity.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_activity.slice(0, 10).map((entry, idx) => (
                  <div
                    key={`${entry.timestamp}-${idx}`}
                    className="flex items-start gap-3 py-2 border-b border-border last:border-0"
                  >
                    <div className="mt-1 shrink-0">
                      <ActivityDot action={entry.action} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="secondary"
                          className="text-[10px] px-1.5 py-0 shrink-0"
                        >
                          {formatActionLabel(entry.action)}
                        </Badge>
                        <span className="text-[11px] text-muted-foreground whitespace-nowrap">
                          {formatRelativeTime(entry.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5 truncate">
                        {entry.details}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Activity className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">No activity yet</p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Activity will appear as you use Hunter
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ActivityDot({ action }: { action: string }) {
  let colorClass = "bg-muted-foreground";

  if (action.includes("submit")) {
    colorClass = "bg-green-500";
  } else if (action.includes("scan") || action.includes("discover")) {
    colorClass = "bg-blue-500";
  } else if (action.includes("review") || action.includes("need")) {
    colorClass = "bg-amber-500";
  } else if (action.includes("fail") || action.includes("error")) {
    colorClass = "bg-red-500";
  } else if (action.includes("start") || action.includes("create")) {
    colorClass = "bg-violet-500";
  }

  return <span className={`block h-2 w-2 rounded-full ${colorClass}`} />;
}

function formatActionLabel(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default DashboardPage;
