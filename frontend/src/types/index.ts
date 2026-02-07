// Job Board types
export interface ScraperConfig {
  scraper_type: "generic" | "workday" | "greenhouse" | "lever";
  selectors: Record<string, string>;
  pagination_type: "click" | "url_param" | "infinite_scroll";
  max_pages: number;
}

export interface Board {
  id: string;
  name: string;
  url: string;
  scan_interval_minutes: number;
  enabled: boolean;
  keyword_filters: string[];
  scraper_config: ScraperConfig;
  last_scanned_at: string | null;
  last_scan_status: string | null;
  last_scan_error: string | null;
  jobs_found_last_scan: number;
  created_at: string;
  updated_at: string;
}

export interface BoardCreate {
  name: string;
  url: string;
  scan_interval_minutes: number;
  enabled: boolean;
  keyword_filters: string[];
  scraper_config: ScraperConfig;
}

// Job types
export interface Job {
  id: string;
  board_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  posted_date: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  description: string;
  match_score: number;
  is_new: boolean;
  is_hidden: boolean;
  created_at: string;
  updated_at: string;
  board_name?: string;
  application_status?: string | null;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobFilters {
  search?: string;
  board_id?: string;
  min_score?: number;
  max_score?: number;
  location?: string;
  is_new?: boolean;
  is_hidden?: boolean;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}

// Profile types
export interface Education {
  id: string;
  school: string;
  degree: string;
  field_of_study: string;
  gpa: string;
  graduation_year: number | null;
}

export interface WorkExperience {
  id: string;
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  description: string;
}

export interface Profile {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  website_url: string;
  us_citizen: boolean | null;
  sponsorship_needed: boolean | null;
  veteran_status: string;
  disability_status: string;
  gender: string;
  ethnicity: string;
  resume_filename: string;
  cover_letter_template: string;
  desired_title: string;
  desired_locations: string;
  min_salary: number | null;
  remote_preference: string;
  education: Education[];
  work_experience: WorkExperience[];
  created_at: string;
  updated_at: string;
}

// Application types
export interface FormField {
  field_name: string;
  field_type: string;
  label: string;
  value: string;
  confidence: number;
  status: "filled" | "needs_input";
  options: string[];
}

export type ApplicationStatus =
  | "pending"
  | "in_progress"
  | "needs_review"
  | "ready_to_submit"
  | "submitted"
  | "failed"
  | "cancelled";

export interface ApplicationLog {
  id: string;
  action: string;
  details: string;
  screenshot_path: string;
  timestamp: string;
}

export interface Application {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  form_fields: FormField[] | null;
  screenshot_path: string;
  current_page_url: string;
  ai_answers: Record<string, string> | null;
  error_message: string;
  celery_task_id: string;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  logs: ApplicationLog[];
  job_title?: string;
  job_company?: string;
}

// Dashboard types
export interface DashboardStats {
  active_boards: number;
  total_jobs: number;
  new_jobs: number;
  in_progress_applications: number;
  needs_review_applications: number;
  submitted_applications: number;
  total_applications: number;
  jobs_by_board: { board: string; count: number }[];
  applications_over_time: { date: string; count: number }[];
  recent_activity: { action: string; details: string; timestamp: string }[];
}

// WebSocket event types
export interface WSEvent {
  type: string;
  data: Record<string, unknown>;
}
