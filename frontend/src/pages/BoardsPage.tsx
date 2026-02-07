import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import { formatRelativeTime } from "@/lib/utils";
import { boardsApi } from "@/lib/api";
import type { Board, BoardCreate, ScraperConfig } from "@/types";
import {
  Plus,
  Pencil,
  Trash2,
  Play,
  Loader2,
  X,
  Globe,
  Clock,
  Upload,
} from "lucide-react";

const SCRAPER_TYPES: ScraperConfig["scraper_type"][] = [
  "generic",
  "workday",
  "greenhouse",
  "lever",
];

const PAGINATION_TYPES: ScraperConfig["pagination_type"][] = [
  "click",
  "url_param",
  "infinite_scroll",
];

function emptyFormData(): BoardCreate {
  return {
    name: "",
    url: "",
    scan_interval_minutes: 60,
    enabled: true,
    keyword_filters: [],
    scraper_config: {
      scraper_type: "generic",
      selectors: {},
      pagination_type: "click",
      max_pages: 5,
    },
  };
}

interface BoardFormProps {
  initial: BoardCreate;
  onSubmit: (data: BoardCreate) => Promise<void>;
  submitLabel: string;
}

function BoardForm({ initial, onSubmit, submitLabel }: BoardFormProps) {
  const [form, setForm] = useState<BoardCreate>(initial);
  const [keywordInput, setKeywordInput] = useState("");
  const [selectorKey, setSelectorKey] = useState("");
  const [selectorValue, setSelectorValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = "Name is required";
    if (!form.url.trim()) errs.url = "URL is required";
    else {
      try {
        new URL(form.url);
      } catch {
        errs.url = "Must be a valid URL";
      }
    }
    if (form.scan_interval_minutes < 1)
      errs.scan_interval_minutes = "Must be at least 1 minute";
    if (form.scraper_config.max_pages < 1)
      errs.max_pages = "Must be at least 1";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit(form);
    } finally {
      setSubmitting(false);
    }
  }

  function addKeyword() {
    const kw = keywordInput.trim();
    if (kw && !form.keyword_filters.includes(kw)) {
      setForm((f) => ({
        ...f,
        keyword_filters: [...f.keyword_filters, kw],
      }));
    }
    setKeywordInput("");
  }

  function removeKeyword(kw: string) {
    setForm((f) => ({
      ...f,
      keyword_filters: f.keyword_filters.filter((k) => k !== kw),
    }));
  }

  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      const newKeywords = text
        .split(/[\n,]+/)
        .map((k) => k.trim())
        .filter(Boolean);
      setForm((f) => {
        const merged = Array.from(
          new Set([...f.keyword_filters, ...newKeywords]),
        );
        return { ...f, keyword_filters: merged };
      });
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  function addSelector() {
    const key = selectorKey.trim();
    const val = selectorValue.trim();
    if (key && val) {
      setForm((f) => ({
        ...f,
        scraper_config: {
          ...f.scraper_config,
          selectors: { ...f.scraper_config.selectors, [key]: val },
        },
      }));
      setSelectorKey("");
      setSelectorValue("");
    }
  }

  function removeSelector(key: string) {
    setForm((f) => {
      const selectors = { ...f.scraper_config.selectors };
      delete selectors[key];
      return {
        ...f,
        scraper_config: { ...f.scraper_config, selectors },
      };
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
      <div className="space-y-2">
        <label className="text-sm font-medium">Name</label>
        <Input
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          placeholder="e.g. Company Careers Page"
        />
        {errors.name && (
          <p className="text-sm text-destructive">{errors.name}</p>
        )}
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">URL</label>
        <Input
          value={form.url}
          onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
          placeholder="https://example.com/careers"
        />
        {errors.url && (
          <p className="text-sm text-destructive">{errors.url}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Scan Interval (minutes)</label>
          <Input
            type="number"
            min={1}
            value={form.scan_interval_minutes}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                scan_interval_minutes: parseInt(e.target.value) || 1,
              }))
            }
          />
          {errors.scan_interval_minutes && (
            <p className="text-sm text-destructive">
              {errors.scan_interval_minutes}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Enabled</label>
          <div className="pt-1">
            <button
              type="button"
              role="switch"
              aria-checked={form.enabled}
              onClick={() => setForm((f) => ({ ...f, enabled: !f.enabled }))}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                form.enabled ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                  form.enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Keyword Filters</label>
        <div className="flex gap-2">
          <Input
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            placeholder="Add keyword..."
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addKeyword();
              }
            }}
          />
          <Button type="button" variant="outline" size="sm" onClick={addKeyword}>
            Add
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.csv"
            className="hidden"
            onChange={handleFileImport}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-4 w-4 mr-1" />
            Import
          </Button>
        </div>
        {form.keyword_filters.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {form.keyword_filters.map((kw) => (
              <Badge key={kw} variant="secondary" className="gap-1">
                {kw}
                <button
                  type="button"
                  onClick={() => removeKeyword(kw)}
                  className="ml-0.5 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="border-t pt-4 space-y-3">
        <h4 className="text-sm font-semibold">Scraper Configuration</h4>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Scraper Type</label>
            <select
              value={form.scraper_config.scraper_type}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  scraper_config: {
                    ...f.scraper_config,
                    scraper_type: e.target
                      .value as ScraperConfig["scraper_type"],
                  },
                }))
              }
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {SCRAPER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Pagination Type</label>
            <select
              value={form.scraper_config.pagination_type}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  scraper_config: {
                    ...f.scraper_config,
                    pagination_type: e.target
                      .value as ScraperConfig["pagination_type"],
                  },
                }))
              }
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {PAGINATION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Max Pages</label>
          <Input
            type="number"
            min={1}
            value={form.scraper_config.max_pages}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                scraper_config: {
                  ...f.scraper_config,
                  max_pages: parseInt(e.target.value) || 1,
                },
              }))
            }
          />
          {errors.max_pages && (
            <p className="text-sm text-destructive">{errors.max_pages}</p>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Custom Selectors</label>
          <div className="flex gap-2">
            <Input
              value={selectorKey}
              onChange={(e) => setSelectorKey(e.target.value)}
              placeholder="Field name (e.g. job_title)"
              className="flex-1"
            />
            <Input
              value={selectorValue}
              onChange={(e) => setSelectorValue(e.target.value)}
              placeholder="CSS selector"
              className="flex-1"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addSelector}
            >
              Add
            </Button>
          </div>
          {Object.keys(form.scraper_config.selectors).length > 0 && (
            <div className="space-y-1 pt-1">
              {Object.entries(form.scraper_config.selectors).map(
                ([key, val]) => (
                  <div
                    key={key}
                    className="flex items-center gap-2 rounded bg-muted px-2 py-1 text-sm"
                  >
                    <span className="font-mono font-medium">{key}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className="font-mono flex-1 truncate text-muted-foreground">
                      {val}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeSelector(key)}
                      className="hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={submitting}>
          {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

function scanStatusBadge(status: string | null) {
  if (!status) return <Badge variant="secondary">Never scanned</Badge>;
  switch (status) {
    case "success":
      return (
        <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
          Success
        </Badge>
      );
    case "running":
      return (
        <Badge className="bg-blue-500/10 text-blue-500 border-blue-500/20">
          Running
        </Badge>
      );
    case "failed":
      return (
        <Badge className="bg-red-500/10 text-red-500 border-red-500/20">
          Failed
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export default function BoardsPage() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editBoard, setEditBoard] = useState<Board | null>(null);
  const [deleteBoard, setDeleteBoard] = useState<Board | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [scanningIds, setScanningIds] = useState<Set<string>>(new Set());

  const fetchBoards = useCallback(async () => {
    try {
      const res = await boardsApi.list();
      setBoards(res.boards);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load boards");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBoards();
  }, [fetchBoards]);

  async function handleCreate(data: BoardCreate) {
    await boardsApi.create(data);
    setCreateOpen(false);
    await fetchBoards();
  }

  async function handleUpdate(data: BoardCreate) {
    if (!editBoard) return;
    await boardsApi.update(editBoard.id, data);
    setEditBoard(null);
    await fetchBoards();
  }

  async function handleDelete() {
    if (!deleteBoard) return;
    setDeleting(true);
    try {
      await boardsApi.delete(deleteBoard.id);
      setDeleteBoard(null);
      await fetchBoards();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete board"
      );
    } finally {
      setDeleting(false);
    }
  }

  async function handleToggleEnabled(board: Board) {
    await boardsApi.update(board.id, { enabled: !board.enabled });
    await fetchBoards();
  }

  async function handleScan(board: Board) {
    setScanningIds((prev) => new Set(prev).add(board.id));
    try {
      await boardsApi.scan(board.id);
      await fetchBoards();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start scan");
    } finally {
      setScanningIds((prev) => {
        const next = new Set(prev);
        next.delete(board.id);
        return next;
      });
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Job Boards</h1>
          <p className="text-muted-foreground">
            Manage your job board sources and scanning configuration.
          </p>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Board
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[560px]">
            <DialogHeader>
              <DialogTitle>Add Job Board</DialogTitle>
              <DialogDescription>
                Configure a new job board to scan for listings.
              </DialogDescription>
            </DialogHeader>
            <BoardForm
              initial={emptyFormData()}
              onSubmit={handleCreate}
              submitLabel="Create Board"
            />
          </DialogContent>
        </Dialog>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
          <button
            className="ml-2 underline"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {boards.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Globe className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No boards configured</h3>
            <p className="text-sm text-muted-foreground mt-1 mb-4">
              Add a job board to start scanning for listings.
            </p>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Board
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {boards.map((board) => (
            <Card key={board.id} className={!board.enabled ? "opacity-60" : ""}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-lg truncate">
                        {board.name}
                      </CardTitle>
                      <Badge variant={board.enabled ? "default" : "secondary"}>
                        {board.enabled ? "Active" : "Disabled"}
                      </Badge>
                      {scanStatusBadge(board.last_scan_status)}
                    </div>
                    <a
                      href={board.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-muted-foreground hover:underline truncate block"
                    >
                      {board.url}
                    </a>
                  </div>

                  <div className="flex items-center gap-1 ml-4 shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleScan(board)}
                      disabled={scanningIds.has(board.id)}
                      title="Run scan now"
                    >
                      {scanningIds.has(board.id) ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </Button>

                    <Dialog
                      open={editBoard?.id === board.id}
                      onOpenChange={(open) => {
                        if (!open) setEditBoard(null);
                        else setEditBoard(board);
                      }}
                    >
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="sm" title="Edit board">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="sm:max-w-[560px]">
                        <DialogHeader>
                          <DialogTitle>Edit Board</DialogTitle>
                          <DialogDescription>
                            Update the configuration for this job board.
                          </DialogDescription>
                        </DialogHeader>
                        <BoardForm
                          initial={{
                            name: board.name,
                            url: board.url,
                            scan_interval_minutes: board.scan_interval_minutes,
                            enabled: board.enabled,
                            keyword_filters: board.keyword_filters,
                            scraper_config: board.scraper_config,
                          }}
                          onSubmit={handleUpdate}
                          submitLabel="Save Changes"
                        />
                      </DialogContent>
                    </Dialog>

                    <Dialog
                      open={deleteBoard?.id === board.id}
                      onOpenChange={(open) => {
                        if (!open) setDeleteBoard(null);
                        else setDeleteBoard(board);
                      }}
                    >
                      <DialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Delete board"
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="sm:max-w-[400px]">
                        <DialogHeader>
                          <DialogTitle>Delete Board</DialogTitle>
                          <DialogDescription>
                            Are you sure you want to delete &quot;{board.name}
                            &quot;? This action cannot be undone.
                          </DialogDescription>
                        </DialogHeader>
                        <div className="flex justify-end gap-2 pt-2">
                          <Button
                            variant="outline"
                            onClick={() => setDeleteBoard(null)}
                          >
                            Cancel
                          </Button>
                          <Button
                            variant="destructive"
                            onClick={handleDelete}
                            disabled={deleting}
                          >
                            {deleting && (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            )}
                            Delete
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
              </CardHeader>

              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <div className="space-y-1">
                    <p className="text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      Scan Interval
                    </p>
                    <p className="font-medium">
                      Every {board.scan_interval_minutes} min
                    </p>
                  </div>

                  <div className="space-y-1">
                    <p className="text-muted-foreground">Last Scanned</p>
                    <p className="font-medium">
                      {board.last_scanned_at
                        ? formatRelativeTime(board.last_scanned_at)
                        : "Never"}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <p className="text-muted-foreground">Jobs Found</p>
                    <p className="font-medium">{board.jobs_found_last_scan}</p>
                  </div>

                  <div className="space-y-1">
                    <p className="text-muted-foreground">Scraper</p>
                    <p className="font-medium capitalize">
                      {board.scraper_config.scraper_type}
                    </p>
                  </div>
                </div>

                {board.last_scan_error && (
                  <div className="mt-3 rounded bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {board.last_scan_error}
                  </div>
                )}

                {board.keyword_filters.length > 0 && (
                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-muted-foreground">
                      Keywords:
                    </span>
                    {board.keyword_filters.map((kw) => (
                      <Badge key={kw} variant="outline" className="text-xs">
                        {kw}
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="mt-3 flex items-center justify-end">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={board.enabled}
                    onClick={() => handleToggleEnabled(board)}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                      board.enabled ? "bg-primary" : "bg-muted"
                    }`}
                  >
                    <span
                      className={`pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                        board.enabled ? "translate-x-4" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
