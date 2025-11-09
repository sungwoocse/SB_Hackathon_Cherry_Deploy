// src/types/deploy.ts

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  reply: string;
  model: string;
}

export interface DeployRequest {
  branch?: string; // default: deploy
}

export type DeployStatusEnum =
  | 'pending'
  | 'running_clone'
  | 'running_build'
  | 'running_cutover'
  | 'running_observability'
  | 'completed'
  | 'failed';

export interface DeployResponse {
  task_id: string;
  status: DeployStatusEnum;
  branch: string;
  action: "deploy" | "rollback";
  queued_at: string;
  estimated_duration_minutes: number;
  context: Record<string, unknown>;
  dev_server_restart_planned: boolean;
}

export interface RiskAssessment {
  risk_level?: string;
  files_changed?: number;
  downtime?: string;
  rollback?: string;
  notes?: string[] | null;
}

export type DiffSource = "working_tree" | "github_compare";

export interface DiffStats {
  file_count?: number;
  added?: number;
  modified?: number;
  deleted?: number;
  lockfile_changed?: boolean;
  env_changed?: boolean;
  config_changed?: boolean;
  sensitive_changed?: boolean;
  test_files_changed?: boolean;
  warnings?: string[];
  [key: string]: unknown;
}

export interface DeployStatusResponse {
  task_id: string;
  status: DeployStatusEnum;
  metadata: Record<string, unknown>;
  stages: Record<string, Record<string, unknown>>;
  started_at: string;
  completed_at?: string | null;
  error_log?: string | null;
  failure_context?: Record<string, unknown> | null;
  risk_assessment?: RiskAssessment | null;
  llm_preview?: LLMPreview | null;
  blue_green_plan?: BlueGreenPlan | null;
  timezone?: string | null;
}

export interface DeployPreviewResponse {
  current_branch: string;
  target_repo: string;
  frontend_project_path?: string | null;
  frontend_output_path?: string | null;
  commands: string[];
  risk_assessment: RiskAssessment;
  llm_preview?: LLMPreview | null;
  timeline_preview: DeployTimelineEntry[];
  warnings: string[];
  task_context?: DeployTaskSummary | null;
  blue_green_plan?: BlueGreenPlan | null;
  timezone?: string | null;
  diff_source: DiffSource;
  diff_stats: DiffStats;
  compare_metadata?: Record<string, unknown> | null;
}

export interface RollbackRequest {
  branch?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  username: string;
  expires_at: string;
}

export interface MeResponse {
  username: string;
}

export interface LogoutResponse {
  success: boolean;
}

export interface ErrorResponse {
  detail: string;
}

export interface DeployTimelineEntry {
  stage: DeployStatusEnum;
  label: string;
  expected_seconds?: number | null;
  completed: boolean;
  status?: string;
  metadata?: Record<string, unknown> | null;
}

export interface DeployTaskSummary {
  task_id: string;
  status: DeployStatusEnum;
  branch: string;
  action: "deploy" | "rollback";
  started_at: string;
  completed_at?: string | null;
  actor?: string | null;
  timezone?: string | null;
  summary?: Record<string, unknown> | null;
  failure_context?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
}

export interface DeployTaskLogResponse {
  task_id: string;
  status: DeployStatusEnum;
  stages: Record<string, Record<string, unknown>>;
  metadata: Record<string, unknown>;
  error_log?: string | null;
  failure_context?: Record<string, unknown> | null;
}

export interface HealthStatusResponse {
  status: string;
  pm2_processes: Record<string, string>;
  mongo: string;
  last_task_id?: string | null;
  last_task_status?: DeployStatusEnum | null;
  issues: string[];
  blue_green?: BlueGreenPlan | null;
}

export interface LLMPreview {
  summary: string;
  highlights: string[];
  risks: string[];
}

export interface BlueGreenPlan {
  active_slot: string;
  standby_slot?: string | null;
  last_cutover_at?: string | null;
  next_cutover_target: string | null;
}
