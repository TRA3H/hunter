import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Archive,
  ChevronDown,
  Clock,
  FileText,
  Loader2,
  Plus,
  Search,
  Trash2,
  ExternalLink,
} from "lucide-react";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { applicationsApi } from "@/lib/api";
import { statusColor, formatRelativeTime } from "@/lib/utils";
import MatchScoreDot from "@/components/MatchScoreDot";
import type { Application, ApplicationStatus } from "@/types";

const ALL_STATUSES: ApplicationStatus[] = [
  "applied",
  "interviewing",
  "offered",
  "rejected",
  "withdrawn",
  "archived",
];

type FilterTab = "all" | ApplicationStatus;

const TABS: { key: FilterTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "applied", label: "Applied" },
  { key: "interviewing", label: "Interviewing" },
  { key: "offered", label: "Offered" },
  { key: "rejected", label: "Rejected" },
  { key: "withdrawn", label: "Withdrawn" },
  { key: "archived", label: "Archived" },
];

function statusLabel(status: ApplicationStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

type SortKey = "updated_at" | "created_at" | "company" | "status" | "match_score";

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [searchInput, setSearchInput] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("updated_at");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [deleting, setDeleting] = useState<Record<string, boolean>>({});
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Add form state
  const [newNotes, setNewNotes] = useState("");
  const [newStatus, setNewStatus] = useState<ApplicationStatus>("applied");
  const [addLoading, setAddLoading] = useState(false);

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await applicationsApi.list();
      setApplications(res.applications);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch applications");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const filtered = useMemo(() => {
    let result = applications;
    if (activeTab !== "all") {
      result = result.filter((app) => app.status === activeTab);
    }
    if (searchInput) {
      const q = searchInput.toLowerCase();
      result = result.filter(
        (app) =>
          (app.job_title && app.job_title.toLowerCase().includes(q)) ||
          (app.job_company && app.job_company.toLowerCase().includes(q)) ||
          app.notes.toLowerCase().includes(q)
      );
    }
    // Sort
    result = [...result].sort((a, b) => {
      switch (sortBy) {
        case "company":
          return (a.job_company || "").localeCompare(b.job_company || "");
        case "status":
          return a.status.localeCompare(b.status);
        case "match_score":
          return (b.match_score ?? 0) - (a.match_score ?? 0);
        case "created_at":
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case "updated_at":
        default:
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      }
    });
    return result;
  }, [applications, activeTab, searchInput, sortBy]);

  const tabCounts = useMemo(() => {
    const counts: Record<FilterTab, number> = { all: applications.length } as Record<FilterTab, number>;
    for (const s of ALL_STATUSES) counts[s] = 0;
    for (const app of applications) {
      if (app.status in counts) counts[app.status as FilterTab]++;
    }
    return counts;
  }, [applications]);

  async function handleAdd() {
    setAddLoading(true);
    try {
      const created = await applicationsApi.create({
        status: newStatus,
        notes: newNotes,
      });
      setApplications((prev) => [created, ...prev]);
      setNewNotes("");
      setNewStatus("applied");
      setShowAddForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create application");
    } finally {
      setAddLoading(false);
    }
  }

  async function handleDelete(id: string) {
    setDeleting((prev) => ({ ...prev, [id]: true }));
    try {
      await applicationsApi.delete(id);
      setApplications((prev) => prev.filter((a) => a.id !== id));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setDeleting((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function handleBulkDelete() {
    if (selectedIds.size === 0) return;
    setBulkDeleting(true);
    try {
      await applicationsApi.bulkDelete(Array.from(selectedIds));
      setApplications((prev) => prev.filter((a) => !selectedIds.has(a.id)));
      setSelectedIds(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk delete failed");
    } finally {
      setBulkDeleting(false);
    }
  }

  async function handleArchive(id: string) {
    try {
      const updated = await applicationsApi.archive(id);
      setApplications((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Archive failed");
    }
  }

  async function handleStatusChange(id: string, status: string) {
    try {
      const updated = await applicationsApi.update(id, { status });
      setApplications((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function handleNotesUpdate(id: string, notes: string) {
    try {
      const updated = await applicationsApi.update(id, { notes });
      setApplications((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((a) => a.id)));
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif tracking-tight">Applications</h1>
          <p className="text-muted-foreground">
            Track and manage your job applications
          </p>
        </div>
        <Button onClick={() => setShowAddForm(!showAddForm)}>
          <Plus className="mr-2 h-4 w-4" />
          Log Application
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto h-auto p-0 text-destructive hover:text-destructive"
            onClick={() => setError(null)}
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Quick-add form */}
      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Log a New Application</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Status</label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value as ApplicationStatus)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {ALL_STATUSES.filter((s) => s !== "archived").map((s) => (
                    <option key={s} value={s}>
                      {statusLabel(s)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Notes</label>
              <Textarea
                value={newNotes}
                onChange={(e) => setNewNotes(e.target.value)}
                placeholder="Company, role, interview date, contact info..."
                rows={3}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleAdd} disabled={addLoading}>
                {addLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save
              </Button>
              <Button variant="ghost" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search + Sort */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by company, role, or notes..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortKey)}
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value="updated_at">Last Updated</option>
          <option value="created_at">Date Applied</option>
          <option value="company">Company</option>
          <option value="status">Status</option>
          <option value="match_score">Match Score</option>
        </select>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 overflow-x-auto rounded-full border bg-muted/50 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
              activeTab === tab.key
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
            <span
              className={`rounded-full px-1.5 py-0.5 text-xs ${
                activeTab === tab.key
                  ? "bg-white/20 text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {tabCounts[tab.key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-2">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleBulkDelete}
            disabled={bulkDeleting}
          >
            {bulkDeleting ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="mr-1 h-3 w-3" />
            )}
            Delete
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {/* Application List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <FileText className="mb-3 h-12 w-12 text-muted-foreground/50" />
            <p className="text-lg font-medium text-muted-foreground">
              No applications found
            </p>
            <p className="mt-1 text-sm text-muted-foreground/80">
              {activeTab === "all"
                ? "Log your first application to start tracking."
                : `No applications with "${activeTab}" status.`}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {/* Select all */}
          <div className="flex items-center gap-2 px-1">
            <input
              type="checkbox"
              checked={selectedIds.size === filtered.length && filtered.length > 0}
              onChange={toggleSelectAll}
              className="h-4 w-4 rounded border-input accent-primary"
            />
            <span className="text-xs text-muted-foreground">Select all</span>
          </div>

          {filtered.map((app) => {
            const isExpanded = expandedId === app.id;

            return (
              <Card
                key={app.id}
                className={`transition-all duration-200 hover:shadow-md hover:border-primary/30 ${
                  selectedIds.has(app.id) ? "border-primary/50 bg-primary/[0.02]" : ""
                }`}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(app.id)}
                      onChange={() => toggleSelect(app.id)}
                      className="mt-1 h-4 w-4 rounded border-input accent-primary"
                      onClick={(e) => e.stopPropagation()}
                    />

                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={() => setExpandedId(isExpanded ? null : app.id)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold leading-tight truncate">
                              {app.job_title || "Untitled Position"}
                            </h3>
                            <Badge variant="secondary" className={statusColor(app.status)}>
                              {statusLabel(app.status)}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {app.job_company || "Unknown Company"}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              Applied {formatRelativeTime(app.created_at)}
                            </span>
                            {app.notes && (
                              <span className="truncate max-w-[200px]">
                                {app.notes}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {app.match_score != null && (
                            <MatchScoreDot score={app.match_score} size="sm" />
                          )}
                          <ChevronDown
                            className={`h-4 w-4 text-muted-foreground transition-transform ${
                              isExpanded ? "rotate-180" : ""
                            }`}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="mt-4 ml-7 space-y-4 border-t pt-4">
                      {/* Status changer */}
                      <div className="flex flex-wrap items-center gap-3">
                        <label className="text-sm font-medium">Status:</label>
                        <select
                          value={app.status}
                          onChange={(e) => handleStatusChange(app.id, e.target.value)}
                          className="flex h-8 rounded-md border border-input bg-transparent px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        >
                          {ALL_STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {statusLabel(s)}
                            </option>
                          ))}
                        </select>

                        {app.job_url && (
                          <Button variant="outline" size="sm" asChild>
                            <a
                              href={app.job_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <ExternalLink className="mr-1 h-3 w-3" />
                              View Posting
                            </a>
                          </Button>
                        )}
                      </div>

                      {/* Notes */}
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium">Notes</label>
                        <Textarea
                          defaultValue={app.notes}
                          onBlur={(e) => {
                            if (e.target.value !== app.notes) {
                              handleNotesUpdate(app.id, e.target.value);
                            }
                          }}
                          placeholder="Interview date, contact info, notes..."
                          rows={3}
                        />
                      </div>

                      {/* Audit log */}
                      {app.logs && app.logs.length > 0 && (
                        <div>
                          <h4 className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <Clock className="h-4 w-4" />
                            Activity Log
                          </h4>
                          <div className="max-h-36 space-y-1.5 overflow-y-auto">
                            {app.logs.map((log) => (
                              <div
                                key={log.id}
                                className="flex items-start gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm"
                              >
                                <span className="shrink-0 text-xs text-muted-foreground">
                                  {formatRelativeTime(log.timestamp)}
                                </span>
                                <span className="font-medium">{log.action}</span>
                                {log.details && (
                                  <span className="text-muted-foreground">{log.details}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-2 border-t pt-3">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleArchive(app.id)}
                        >
                          <Archive className="mr-1 h-3 w-3" />
                          Archive
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => handleDelete(app.id)}
                          disabled={deleting[app.id]}
                        >
                          {deleting[app.id] ? (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          ) : (
                            <Trash2 className="mr-1 h-3 w-3" />
                          )}
                          Delete
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
