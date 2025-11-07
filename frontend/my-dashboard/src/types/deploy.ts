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
}

export interface DeployStatusResponse {
  task_id: string;
  status: DeployStatusEnum;
  metadata: Record<string, any>;
  started_at: string;
  completed_at?: string | null;
  error_log?: string | null;
}

export interface DeployPreviewResponse {
  current_branch: string;
  target_repo: string;
  frontend_project_path?: string | null;
  frontend_output_path?: string | null;
  commands: string[];
  risk_assessment: Record<string, any>;
  cost_estimate: Record<string, any>;
  llm_preview?: Record<string, any> | null;
}

export interface RollbackRequest {
  branch?: string;
}

export interface ErrorResponse {
  detail: string;
}
