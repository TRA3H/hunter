import type {
  Application,
  Board,
  BoardCreate,
  DashboardStats,
  Job,
  JobFilters,
  JobListResponse,
  Profile,
} from "@/types";

const API_BASE = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Boards
export const boardsApi = {
  list: () => request<{ boards: Board[]; total: number }>("/api/boards"),
  get: (id: string) => request<Board>(`/api/boards/${id}`),
  create: (data: BoardCreate) => request<Board>("/api/boards", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<BoardCreate>) =>
    request<Board>(`/api/boards/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/api/boards/${id}`, { method: "DELETE" }),
  scan: (id: string) => request<{ task_id: string }>(`/api/boards/${id}/scan`, { method: "POST" }),
};

// Jobs
export const jobsApi = {
  list: (filters?: JobFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          params.set(key, String(value));
        }
      });
    }
    return request<JobListResponse>(`/api/jobs?${params}`);
  },
  get: (id: string) => request<Job>(`/api/jobs/${id}`),
  hide: (id: string) => request<Job>(`/api/jobs/${id}/hide`, { method: "PATCH" }),
  markRead: (id: string) => request<Job>(`/api/jobs/${id}/read`, { method: "PATCH" }),
};

// Profile
export const profileApi = {
  get: () => request<Profile>("/api/profile"),
  update: (data: Partial<Profile>) =>
    request<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(data) }),
  uploadResume: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/profile/resume`, { method: "POST", body: formData });
    if (!res.ok) throw new Error("Failed to upload resume");
    return res.json() as Promise<Profile>;
  },
  addEducation: (data: Omit<import("@/types").Education, "id">) =>
    request<import("@/types").Education>("/api/profile/education", { method: "POST", body: JSON.stringify(data) }),
  deleteEducation: (id: string) => request<void>(`/api/profile/education/${id}`, { method: "DELETE" }),
  addExperience: (data: Omit<import("@/types").WorkExperience, "id">) =>
    request<import("@/types").WorkExperience>("/api/profile/experience", { method: "POST", body: JSON.stringify(data) }),
  deleteExperience: (id: string) => request<void>(`/api/profile/experience/${id}`, { method: "DELETE" }),
};

// Applications
export const applicationsApi = {
  list: (status?: string, search?: string, job_id?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    if (job_id) params.set("job_id", job_id);
    const qs = params.toString();
    return request<{ applications: Application[]; total: number }>(`/api/applications${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => request<Application>(`/api/applications/${id}`),
  create: (data: { job_id?: string; status?: string; notes?: string; applied_via?: string }) =>
    request<Application>("/api/applications", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: { status?: string; notes?: string }) =>
    request<Application>(`/api/applications/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/api/applications/${id}`, { method: "DELETE" }),
  archive: (id: string) => request<Application>(`/api/applications/${id}/archive`, { method: "POST" }),
  bulkDelete: (ids: string[]) =>
    request<void>("/api/applications/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  dashboard: () => request<DashboardStats>("/api/applications/dashboard"),
};
