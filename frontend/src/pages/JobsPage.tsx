import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useJobs } from "@/hooks/useJobs";
import { jobsApi, applicationsApi, boardsApi } from "@/lib/api";
import {
  formatDate,
  formatSalary,
  scoreBgColor,
  statusColor,
  formatRelativeTime,
} from "@/lib/utils";
import MatchScoreDot from "@/components/MatchScoreDot";
import type { Job, Board } from "@/types";
import {
  Search,
  MapPin,
  Building2,
  DollarSign,
  Eye,
  EyeOff,
  Send,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Loader2,
  SlidersHorizontal,
} from "lucide-react";

function JobsPage() {
  const {
    jobs,
    total,
    page,
    page_size,
    filters,
    updateFilters,
    loading,
    error,
    refresh,
  } = useJobs({ is_hidden: false });

  const [boards, setBoards] = useState<Board[]>([]);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [applyingJobId, setApplyingJobId] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Local filter state for controlled inputs
  const [localMinScore, setLocalMinScore] = useState(filters.min_score ?? 0);
  const [localLocation, setLocalLocation] = useState(filters.location ?? "");

  useEffect(() => {
    boardsApi.list().then((res) => setBoards(res.boards)).catch(() => {});
  }, []);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / page_size)),
    [total, page_size]
  );

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== (filters.search ?? "")) {
        updateFilters({ search: searchInput || undefined });
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleHide = useCallback(
    async (job: Job) => {
      setActionLoadingId(job.id);
      try {
        await jobsApi.hide(job.id);
        refresh();
      } catch {
        // silently fail
      } finally {
        setActionLoadingId(null);
      }
    },
    [refresh]
  );

  const handleMarkRead = useCallback(
    async (job: Job) => {
      setActionLoadingId(job.id);
      try {
        await jobsApi.markRead(job.id);
        refresh();
      } catch {
        // silently fail
      } finally {
        setActionLoadingId(null);
      }
    },
    [refresh]
  );

  const handleAutoApply = useCallback(async (jobId: string) => {
    setApplyingJobId(jobId);
    try {
      await applicationsApi.create(jobId);
    } catch {
      // silently fail
    } finally {
      setApplyingJobId(null);
    }
  }, []);

  const handleLocationCommit = useCallback(() => {
    if (localLocation !== (filters.location ?? "")) {
      updateFilters({ location: localLocation || undefined });
    }
  }, [localLocation, filters.location, updateFilters]);

  const handleScoreCommit = useCallback(() => {
    const value = localMinScore > 0 ? localMinScore : undefined;
    if (value !== filters.min_score) {
      updateFilters({ min_score: value });
    }
  }, [localMinScore, filters.min_score, updateFilters]);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif tracking-tight">Jobs</h1>
          <p className="text-muted-foreground">
            {total} job{total !== 1 ? "s" : ""} found
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setFiltersOpen((o) => !o)}
        >
          <SlidersHorizontal className="mr-2 h-4 w-4" />
          Filters
        </Button>
      </div>

      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search jobs by title, company, or keywords..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Filters panel */}
      {filtersOpen && (
        <Card>
          <CardContent className="grid gap-4 pt-6 sm:grid-cols-2 lg:grid-cols-4">
            {/* Board dropdown */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Board</label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={filters.board_id ?? ""}
                onChange={(e) =>
                  updateFilters({
                    board_id: e.target.value || undefined,
                  })
                }
              >
                <option value="">All boards</option>
                {boards.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Min match score slider */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                Min match score: {localMinScore}%
              </label>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={localMinScore}
                onChange={(e) => setLocalMinScore(Number(e.target.value))}
                onMouseUp={handleScoreCommit}
                onTouchEnd={handleScoreCommit}
                className="w-full accent-primary"
              />
            </div>

            {/* Location */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Location</label>
              <Input
                placeholder="e.g. Remote, New York..."
                value={localLocation}
                onChange={(e) => setLocalLocation(e.target.value)}
                onBlur={handleLocationCommit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLocationCommit();
                }}
              />
            </div>

            {/* New only toggle */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Show only new</label>
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  role="switch"
                  aria-checked={filters.is_new === true}
                  onClick={() =>
                    updateFilters({
                      is_new: filters.is_new ? undefined : true,
                    })
                  }
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    filters.is_new ? "bg-primary" : "bg-muted"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition-transform ${
                      filters.is_new ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
                <span className="text-sm text-muted-foreground">
                  {filters.is_new ? "On" : "Off"}
                </span>
              </div>
            </div>

            {/* Sort by */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Sort by</label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={filters.sort_by ?? "created_at"}
                onChange={(e) => updateFilters({ sort_by: e.target.value })}
              >
                <option value="created_at">Date added</option>
                <option value="posted_date">Posted date</option>
                <option value="match_score">Match score</option>
                <option value="title">Title</option>
                <option value="company">Company</option>
              </select>
            </div>

            {/* Sort order */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Order</label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={filters.sort_order ?? "desc"}
                onChange={(e) => updateFilters({ sort_order: e.target.value })}
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>

            {/* Reset */}
            <div className="flex items-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearchInput("");
                  setLocalMinScore(0);
                  setLocalLocation("");
                  updateFilters({
                    search: undefined,
                    board_id: undefined,
                    min_score: undefined,
                    location: undefined,
                    is_new: undefined,
                    sort_by: undefined,
                    sort_order: undefined,
                  });
                }}
              >
                Reset all filters
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="py-4 text-center text-destructive">
            {error}
            <Button variant="link" onClick={refresh} className="ml-2">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">Loading jobs...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && jobs.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No jobs match your current filters. Try adjusting your search
            criteria.
          </CardContent>
        </Card>
      )}

      {/* Job cards */}
      {!loading && (
        <div className="space-y-3">
          {jobs.map((job) => {
            const isExpanded = expandedJobId === job.id;
            const isActioning = actionLoadingId === job.id;
            const isApplying = applyingJobId === job.id;
            const salary = formatSalary(
              job.salary_min,
              job.salary_max,
              job.salary_currency
            );

            return (
              <Card
                key={job.id}
                className={`transition-all duration-200 hover:border-primary/30 ${
                  job.is_new
                    ? "border-primary/30 bg-primary/[0.02]"
                    : ""
                }`}
              >
                <CardContent className="p-4">
                  {/* Main row */}
                  <div
                    className="flex cursor-pointer items-start justify-between gap-4"
                    onClick={() =>
                      setExpandedJobId(isExpanded ? null : job.id)
                    }
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold leading-tight">
                          {job.title}
                        </h3>
                        {job.is_new && (
                          <Badge variant="secondary" className="text-xs">
                            New
                          </Badge>
                        )}
                        {job.application_status && (
                          <Badge
                            variant="outline"
                            className={statusColor(job.application_status)}
                          >
                            {job.application_status.replace("_", " ")}
                          </Badge>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Building2 className="h-3.5 w-3.5" />
                          {job.company}
                        </span>
                        {job.location && (
                          <span className="flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5" />
                            {job.location}
                          </span>
                        )}
                        {salary && (
                          <span className="flex items-center gap-1">
                            <DollarSign className="h-3.5 w-3.5" />
                            {salary}
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        {job.posted_date && (
                          <span>
                            Posted {formatDate(job.posted_date)}
                          </span>
                        )}
                        <span>
                          Added {formatRelativeTime(job.created_at)}
                        </span>
                        {job.board_name && (
                          <span className="rounded bg-muted px-1.5 py-0.5">
                            {job.board_name}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Match score */}
                    <MatchScoreDot score={job.match_score} size="lg" />
                  </div>

                  {/* Expanded description */}
                  {isExpanded && (
                    <div className="mt-4 space-y-4">
                      <div className="rounded-md bg-muted/50 p-4">
                        <p className="whitespace-pre-wrap text-sm leading-relaxed">
                          {job.description || "No description available."}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isActioning}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleMarkRead(job);
                          }}
                        >
                          {isActioning ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Eye className="mr-1.5 h-3.5 w-3.5" />
                          )}
                          Mark Read
                        </Button>

                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isActioning}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleHide(job);
                          }}
                        >
                          {isActioning ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <EyeOff className="mr-1.5 h-3.5 w-3.5" />
                          )}
                          Hide
                        </Button>

                        <Button
                          size="sm"
                          disabled={isApplying || !!job.application_status}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAutoApply(job.id);
                          }}
                        >
                          {isApplying ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Send className="mr-1.5 h-3.5 w-3.5" />
                          )}
                          {job.application_status
                            ? "Applied"
                            : "Auto-Apply"}
                        </Button>

                        {job.url && (
                          <Button
                            size="sm"
                            variant="ghost"
                            asChild
                          >
                            <a
                              href={job.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                              View posting
                            </a>
                          </Button>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => updateFilters({ page: page - 1 })}
            >
              <ChevronLeft className="mr-1 h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => updateFilters({ page: page + 1 })}
            >
              Next
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default JobsPage;
