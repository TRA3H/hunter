import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Send,
  XCircle,
  Bot,
  Loader2,
  Clock,
  FileText,
  Image,
  ExternalLink,
} from "lucide-react";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { applicationsApi } from "@/lib/api";
import { statusColor, formatRelativeTime } from "@/lib/utils";
import type { Application, ApplicationStatus, FormField } from "@/types";

type FilterTab = "all" | "needs_review" | "in_progress" | "submitted" | "failed";

const TABS: { key: FilterTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_review", label: "Needs Review" },
  { key: "in_progress", label: "In Progress" },
  { key: "submitted", label: "Submitted" },
  { key: "failed", label: "Failed" },
];

function statusLabel(status: ApplicationStatus): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function screenshotUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  // Strip any leading path components, keep just the filename
  const filename = path.split("/").pop() || path;
  const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
  return `${apiBase}/uploads/screenshots/${filename}`;
}

export default function AutoApplyPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editedFields, setEditedFields] = useState<Record<string, FormField[]>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});
  const [aiLoading, setAiLoading] = useState<Record<string, boolean>>({});
  const [cancelling, setCancelling] = useState<Record<string, boolean>>({});

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
    if (activeTab === "all") return applications;
    return applications.filter((app) => app.status === activeTab);
  }, [applications, activeTab]);

  const tabCounts = useMemo(() => {
    const counts: Record<FilterTab, number> = {
      all: applications.length,
      needs_review: 0,
      in_progress: 0,
      submitted: 0,
      failed: 0,
    };
    for (const app of applications) {
      if (app.status === "needs_review") counts.needs_review++;
      else if (app.status === "in_progress" || app.status === "pending") counts.in_progress++;
      else if (app.status === "submitted") counts.submitted++;
      else if (app.status === "failed" || app.status === "cancelled") counts.failed++;
    }
    return counts;
  }, [applications]);

  function getEditableFields(app: Application): FormField[] {
    if (editedFields[app.id]) return editedFields[app.id];
    return app.form_fields ? app.form_fields.map((f) => ({ ...f })) : [];
  }

  function updateField(appId: string, fieldIndex: number, value: string) {
    const current = getEditableFields(
      applications.find((a) => a.id === appId)!,
    );
    const updated = current.map((f, i) =>
      i === fieldIndex ? { ...f, value, status: "filled" as const } : f,
    );
    setEditedFields((prev) => ({ ...prev, [appId]: updated }));
  }

  async function handleAiAssist(app: Application) {
    setAiLoading((prev) => ({ ...prev, [app.id]: true }));
    try {
      const res = await applicationsApi.aiAssist(app.id);
      const current = getEditableFields(app);
      const updated = current.map((field) => {
        const suggestion = res.answers[field.field_name];
        if (suggestion) {
          return { ...field, value: suggestion, status: "filled" as const };
        }
        return field;
      });
      setEditedFields((prev) => ({ ...prev, [app.id]: updated }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI Assist failed");
    } finally {
      setAiLoading((prev) => ({ ...prev, [app.id]: false }));
    }
  }

  async function handleSubmitReview(app: Application) {
    const fields = getEditableFields(app);
    setSubmitting((prev) => ({ ...prev, [app.id]: true }));
    try {
      const updated = await applicationsApi.review(app.id, fields);
      setApplications((prev) =>
        prev.map((a) => (a.id === updated.id ? updated : a)),
      );
      setEditedFields((prev) => {
        const next = { ...prev };
        delete next[app.id];
        return next;
      });
      setExpandedId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting((prev) => ({ ...prev, [app.id]: false }));
    }
  }

  async function handleCancel(app: Application) {
    setCancelling((prev) => ({ ...prev, [app.id]: true }));
    try {
      const updated = await applicationsApi.cancel(app.id);
      setApplications((prev) =>
        prev.map((a) => (a.id === updated.id ? updated : a)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setCancelling((prev) => ({ ...prev, [app.id]: false }));
    }
  }

  function renderFieldInput(
    app: Application,
    field: FormField,
    index: number,
  ) {
    const isDisabled = submitting[app.id] || false;

    if (field.field_type === "textarea") {
      return (
        <Textarea
          value={field.value}
          onChange={(e) => updateField(app.id, index, e.target.value)}
          disabled={isDisabled}
          placeholder={field.label}
          rows={3}
          className="mt-1"
        />
      );
    }

    if (field.field_type === "select" && field.options.length > 0) {
      return (
        <select
          value={field.value}
          onChange={(e) => updateField(app.id, index, e.target.value)}
          disabled={isDisabled}
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Select...</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    }

    return (
      <Input
        value={field.value}
        onChange={(e) => updateField(app.id, index, e.target.value)}
        disabled={isDisabled}
        placeholder={field.label}
        className="mt-1"
      />
    );
  }

  function renderReviewPanel(app: Application) {
    const fields = getEditableFields(app);
    const hasUnfilled = fields.some((f) => f.status === "needs_input");
    const isSubmitting = submitting[app.id] || false;
    const isAiLoading = aiLoading[app.id] || false;

    return (
      <div className="mt-4 space-y-6">
        {/* Screenshot */}
        {app.screenshot_path && (
          <div>
            <h4 className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Image className="h-4 w-4" />
              Application Screenshot
            </h4>
            <div className="overflow-auto rounded-lg border max-h-[500px]">
              <img
                src={screenshotUrl(app.screenshot_path)}
                alt="Application form screenshot"
                className="w-full min-w-[1280px]"
              />
            </div>
          </div>
        )}

        {/* Form Fields */}
        {fields.length > 0 && (
          <div>
            <h4 className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <FileText className="h-4 w-4" />
              Form Fields
            </h4>
            <div className="space-y-4">
              {fields.map((field, idx) => (
                <div
                  key={field.field_name}
                  className="rounded-lg border p-3"
                >
                  <div className="mb-1 flex items-center gap-2">
                    {field.status === "filled" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-yellow-500" />
                    )}
                    <label className="text-sm font-medium">
                      {field.label}
                    </label>
                    {field.confidence > 0 && (
                      <span className="ml-auto text-xs text-muted-foreground">
                        {Math.round(field.confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                  {field.status === "needs_input" ? (
                    renderFieldInput(app, field, idx)
                  ) : (
                    <div className="mt-1">
                      <Input
                        value={field.value}
                        onChange={(e) =>
                          updateField(app.id, idx, e.target.value)
                        }
                        disabled={isSubmitting}
                        className="mt-1"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-3 border-t pt-4">
          {app.current_page_url && (
            <Button
              variant="outline"
              asChild
            >
              <a
                href={app.current_page_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="mr-2 h-4 w-4" />
                Open in Browser
              </a>
            </Button>
          )}
          <Button
            onClick={() => handleAiAssist(app)}
            disabled={isAiLoading || isSubmitting}
            variant="outline"
          >
            {isAiLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Bot className="mr-2 h-4 w-4" />
            )}
            AI Assist
          </Button>
          <Button
            onClick={() => handleSubmitReview(app)}
            disabled={isSubmitting || (hasUnfilled && !editedFields[app.id])}
          >
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Submit Application
          </Button>
          <Button
            variant="ghost"
            onClick={() => handleCancel(app)}
            disabled={cancelling[app.id]}
            className="text-destructive hover:text-destructive"
          >
            {cancelling[app.id] ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <XCircle className="mr-2 h-4 w-4" />
            )}
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  function renderAuditLog(app: Application) {
    if (!app.logs || app.logs.length === 0) return null;

    return (
      <div className="mt-4 border-t pt-4">
        <h4 className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Clock className="h-4 w-4" />
          Audit Log
        </h4>
        <div className="max-h-48 space-y-2 overflow-y-auto">
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
    );
  }

  function renderApplicationCard(app: Application) {
    const isExpanded = expandedId === app.id;
    const canCancel =
      app.status !== "submitted" &&
      app.status !== "cancelled" &&
      app.status !== "failed";

    return (
      <Card key={app.id} className={`transition-all duration-200 hover:shadow-md hover:border-primary/30 ${app.status === "needs_review" ? "animate-gentle-pulse" : ""}`}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <CardTitle className="truncate text-lg">
                {app.job_title || "Untitled Position"}
              </CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {app.job_company || "Unknown Company"}
              </p>
            </div>
            <Badge
              variant="secondary"
              className={statusColor(app.status)}
            >
              {statusLabel(app.status)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Created {formatRelativeTime(app.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Updated {formatRelativeTime(app.updated_at)}
            </span>
            {app.error_message && (
              <span className="flex items-center gap-1 text-destructive">
                <AlertTriangle className="h-3 w-3" />
                {app.error_message}
              </span>
            )}
          </div>

          {/* Quick actions row for non-expanded cards */}
          {!isExpanded && (
            <div className="mt-3 flex items-center gap-2">
              {app.status === "needs_review" && (
                <Button
                  size="sm"
                  onClick={() => setExpandedId(app.id)}
                >
                  <FileText className="mr-1 h-3 w-3" />
                  Review
                </Button>
              )}
              {canCancel && app.status !== "needs_review" && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleCancel(app)}
                  disabled={cancelling[app.id]}
                  className="text-destructive hover:text-destructive"
                >
                  {cancelling[app.id] ? (
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  ) : (
                    <XCircle className="mr-1 h-3 w-3" />
                  )}
                  Cancel
                </Button>
              )}
            </div>
          )}

          {/* Review Panel */}
          {isExpanded && app.status === "needs_review" && (
            <>
              {renderReviewPanel(app)}
              <div className="mt-2 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setExpandedId(null)}
                >
                  Collapse
                </Button>
              </div>
            </>
          )}

          {/* Audit Log (visible when expanded or always for needs_review) */}
          {isExpanded && renderAuditLog(app)}

          {/* Expand toggle for audit log on non-review items */}
          {!isExpanded && app.logs && app.logs.length > 0 && (
            <Button
              variant="link"
              size="sm"
              className="mt-2 h-auto p-0 text-xs"
              onClick={() => setExpandedId(app.id)}
            >
              View audit log ({app.logs.length} entries)
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="text-3xl font-serif tracking-tight">Auto-Apply</h1>
        <p className="text-muted-foreground">
          Review and manage automated job applications
        </p>
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

      {/* Filter Tabs */}
      <div className="flex gap-1 rounded-full border bg-muted/50 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
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
              {tabCounts[tab.key]}
            </span>
          </button>
        ))}
      </div>

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
                ? "Start applying to jobs to see them here."
                : `No applications with status "${activeTab.replace(/_/g, " ")}".`}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filtered.map((app) => renderApplicationCard(app))}
        </div>
      )}
    </div>
  );
}
