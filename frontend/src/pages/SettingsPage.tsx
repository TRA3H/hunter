import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Bell,
  Clock,
  Download,
  Trash2,
  Save,
  Settings,
} from "lucide-react";
import { jobsApi } from "@/lib/api";

const STORAGE_KEY = "hunter_settings";

interface HunterSettings {
  emailNotifications: boolean;
  notificationEmail: string;
  alertMode: "instant" | "digest";
  minMatchScoreAlerts: number;

  scanOnStartup: boolean;
  activeHoursOnly: boolean;
  startHour: number;
  endHour: number;
}

const DEFAULT_SETTINGS: HunterSettings = {
  emailNotifications: false,
  notificationEmail: "",
  alertMode: "instant",
  minMatchScoreAlerts: 70,

  scanOnStartup: true,
  activeHoursOnly: false,
  startHour: 8,
  endHour: 18,
};

function loadSettings(): HunterSettings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch {
    // Corrupted data; fall through to defaults
  }
  return { ...DEFAULT_SETTINGS };
}

function saveSettings(settings: HunterSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent
        transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2
        focus-visible:ring-ring focus-visible:ring-offset-2
        ${checked ? "bg-primary" : "bg-muted"}
      `}
    >
      <span
        className={`
          pointer-events-none inline-block h-5 w-5 rounded-full bg-background shadow-lg ring-0
          transition-transform duration-200 ease-in-out
          ${checked ? "translate-x-5" : "translate-x-0"}
        `}
      />
    </button>
  );
}

function Slider({
  value,
  onChange,
  min,
  max,
  label,
}: {
  value: number;
  onChange: (val: number) => void;
  min: number;
  max: number;
  label: string;
}) {
  return (
    <input
      type="range"
      min={min}
      max={max}
      value={value}
      aria-label={label}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-muted accent-primary"
    />
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<HunterSettings>(loadSettings);
  const [saved, setSaved] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const update = useCallback(
    <K extends keyof HunterSettings>(key: K, value: HunterSettings[K]) => {
      setSettings((prev) => {
        const next = { ...prev, [key]: value };
        saveSettings(next);
        return next;
      });
      setSaved(false);
    },
    []
  );

  useEffect(() => {
    if (saved) {
      const timer = setTimeout(() => setSaved(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [saved]);

  const handleExportData = async () => {
    try {
      const data = await jobsApi.list({ page_size: 9999 });
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `hunter-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export data:", err);
      alert("Failed to export data. Check the console for details.");
    }
  };

  const handleResetHistory = async () => {
    try {
      await fetch("/api/scan-history", { method: "DELETE" });
    } catch {
      // Best-effort; the API may not exist yet
    }
    setShowResetConfirm(false);
  };

  const handleSaveAll = () => {
    saveSettings(settings);
    setSaved(true);
  };

  return (
    <div className="container mx-auto max-w-3xl py-8 px-4 space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="h-7 w-7 text-muted-foreground" />
          <div>
            <h1 className="text-3xl font-serif tracking-tight">Settings</h1>
            <p className="text-sm text-muted-foreground">
              Configure your job search automation preferences
            </p>
          </div>
        </div>
        <Button onClick={handleSaveAll} className="gap-2">
          <Save className="h-4 w-4" />
          {saved ? "Saved" : "Save All"}
        </Button>
      </div>

      {saved && (
        <Badge variant="secondary" className="text-green-600">
          Settings saved successfully
        </Badge>
      )}

      {/* Notification Preferences */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Notification Preferences</CardTitle>
          </div>
          <CardDescription>
            Control how and when you receive job match alerts
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Email Notifications</p>
              <p className="text-xs text-muted-foreground">
                Receive alerts via email when new matches are found
              </p>
            </div>
            <Toggle
              checked={settings.emailNotifications}
              onChange={(val) => update("emailNotifications", val)}
              label="Email notifications"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="notification-email">
              Notification Email
            </label>
            <Input
              id="notification-email"
              type="email"
              placeholder="you@example.com"
              value={settings.notificationEmail}
              disabled={!settings.emailNotifications}
              onChange={(e) => update("notificationEmail", e.target.value)}
            />
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">Alert Mode</p>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="alertMode"
                  value="instant"
                  checked={settings.alertMode === "instant"}
                  onChange={() => update("alertMode", "instant")}
                  className="accent-primary"
                />
                <span className="text-sm">Instant</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="alertMode"
                  value="digest"
                  checked={settings.alertMode === "digest"}
                  onChange={() => update("alertMode", "digest")}
                  className="accent-primary"
                />
                <span className="text-sm">Digest (every 30 min)</span>
              </label>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Minimum Match Score for Alerts</p>
              <Badge variant="outline">{settings.minMatchScoreAlerts}%</Badge>
            </div>
            <Slider
              value={settings.minMatchScoreAlerts}
              onChange={(val) => update("minMatchScoreAlerts", val)}
              min={0}
              max={100}
              label="Minimum match score for alerts"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Scan Behavior */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Scan Behavior</CardTitle>
          </div>
          <CardDescription>
            Control when and how job scanning runs
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Scan on Startup</p>
              <p className="text-xs text-muted-foreground">
                Automatically start scanning when the app launches
              </p>
            </div>
            <Toggle
              checked={settings.scanOnStartup}
              onChange={(val) => update("scanOnStartup", val)}
              label="Scan on startup"
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Active Hours Only</p>
              <p className="text-xs text-muted-foreground">
                Only scan during the specified time window
              </p>
            </div>
            <Toggle
              checked={settings.activeHoursOnly}
              onChange={(val) => update("activeHoursOnly", val)}
              label="Active hours only"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="start-hour">
                Start Hour (0-23)
              </label>
              <Input
                id="start-hour"
                type="number"
                min={0}
                max={23}
                value={settings.startHour}
                disabled={!settings.activeHoursOnly}
                onChange={(e) => {
                  const val = Math.max(0, Math.min(23, Number(e.target.value)));
                  update("startHour", val);
                }}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="end-hour">
                End Hour (0-23)
              </label>
              <Input
                id="end-hour"
                type="number"
                min={0}
                max={23}
                value={settings.endHour}
                disabled={!settings.activeHoursOnly}
                onChange={(e) => {
                  const val = Math.max(0, Math.min(23, Number(e.target.value)));
                  update("endHour", val);
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Data Management */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Download className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Data Management</CardTitle>
          </div>
          <CardDescription>
            Export your data or reset scan history
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Export All Data</p>
              <p className="text-xs text-muted-foreground">
                Download all tracked jobs as a JSON file
              </p>
            </div>
            <Button variant="outline" onClick={handleExportData} className="gap-2">
              <Download className="h-4 w-4" />
              Export
            </Button>
          </div>

          <div className="border-t border-destructive/20 pt-4 mt-4 rounded-lg bg-destructive/5 p-4 -mx-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-destructive">Reset Scan History</p>
                <p className="text-xs text-muted-foreground">
                  Clear all scan history data. This cannot be undone.
                </p>
              </div>
              {!showResetConfirm ? (
                <Button
                  variant="destructive"
                  onClick={() => setShowResetConfirm(true)}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  Reset
                </Button>
              ) : (
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowResetConfirm(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleResetHistory}
                    className="gap-2"
                  >
                    <Trash2 className="h-4 w-4" />
                    Confirm Reset
                  </Button>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
