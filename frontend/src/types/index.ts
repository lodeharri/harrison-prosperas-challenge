export type JobStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface Job {
  job_id: string;
  user_id: string;
  status: JobStatus;
  report_type: string;
  date_range: string;
  format: 'pdf' | 'csv' | 'excel';
  created_at: string;
  updated_at: string;
  result_url: string | null;
}

export interface JobCreateRequest {
  report_type: string;
  date_range?: string;
  format?: 'pdf' | 'csv' | 'excel';
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
  idempotent?: boolean;
}

export interface JobListResponse {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenRequest {
  user_id: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface WebSocketMessage {
  type: 'job_update';
  data: {
    job_id: string;
    status: JobStatus;
    result_url?: string;
    updated_at: string;
  };
}
