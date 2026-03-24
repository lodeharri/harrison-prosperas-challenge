import axios, { type AxiosInstance } from 'axios';
import type { 
  Job, 
  JobCreateRequest, 
  JobCreateResponse, 
  JobListResponse,
  TokenResponse
} from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

/**
 * Generate a unique idempotency key using browser crypto API.
 */
export function generateIdempotencyKey(): string {
  return crypto.randomUUID();
}

/**
 * Decode JWT payload to extract user information.
 * Returns null if token is invalid.
 */
export function decodeJwtPayload(token: string): { sub: string; exp: number; iat: number } | null {
  try {
    const base64Url = token.split('.')[1];
    if (!base64Url) return null;
    
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    // Use atob for browser environment
    const jsonPayload = atob(base64);
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

class ApiService {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });

    this.token = localStorage.getItem('token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  getUserId(): string | null {
    if (!this.token) return null;
    const payload = decodeJwtPayload(this.token);
    return payload?.sub || null;
  }

  async requestToken(userId: string): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>('/auth/token', { user_id: userId });
    this.setToken(response.data.access_token);
    return response.data;
  }

  async createJob(data: JobCreateRequest, idempotencyKey?: string): Promise<JobCreateResponse> {
    const config = idempotencyKey ? { headers: { 'X-Idempotency-Key': idempotencyKey } } : {};
    const response = await this.client.post<JobCreateResponse>('/jobs', data, config);
    return response.data;
  }

  async getJobs(page: number = 1, pageSize: number = 20): Promise<JobListResponse> {
    const response = await this.client.get<JobListResponse>('/jobs', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  async getJob(jobId: string): Promise<Job> {
    const response = await this.client.get<Job>(`/jobs/${jobId}`);
    return response.data;
  }

  async getHealth() {
    const response = await this.client.get('/health');
    return response.data;
  }

  getWebSocketUrl(userId: string): string {
    const token = this.token || '';
    return `${WS_URL}/ws/jobs?user_id=${encodeURIComponent(userId)}&token=${encodeURIComponent(token)}`;
  }
}

export const apiService = new ApiService();
export { API_URL, WS_URL };
