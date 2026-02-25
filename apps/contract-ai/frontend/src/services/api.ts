/**
 * API Service for Contract-AI-System
 *
 * Handles all HTTP requests to the FastAPI backend
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { toast } from 'react-hot-toast';

// Types
export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  subscription_tier: string;
  is_demo: boolean;
  email_verified: boolean;
  created_at: string;
  last_login?: string;
  contracts_today: number;
  llm_requests_today: number;
  demo_expires?: string;
}

export interface LoginRequest {
  username: string;  // FastAPI OAuth2 uses 'username' field
  password: string;
}

export interface RegisterRequest {
  email: string;
  name: string;
  password: string;
}

export interface DemoActivateRequest {
  token: string;
  email: string;
  name: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface DemoLinkResponse {
  token: string;
  url: string;
  expires_at: string;
  max_contracts: number;
  max_llm_requests: number;
}

// API Client
class APIClient {
  private client: AxiosInstance;
  private refreshing = false;

  constructor() {
    const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor: Add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor: Handle errors and token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // Handle 401 errors (token expired)
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          // Try to refresh token
          const refreshed = await this.refreshToken();
          if (refreshed) {
            return this.client(originalRequest);
          }

          // Refresh failed, redirect to login
          this.logout();
          window.location.href = '/login';
        }

        // Handle rate limiting
        if (error.response?.status === 429) {
          toast.error('Слишком много запросов. Пожалуйста, подождите.');
        }

        return Promise.reject(error);
      }
    );
  }

  // ==================== Token Management ====================

  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('access_token');
  }

  private getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('refresh_token');
  }

  private setTokens(accessToken: string, refreshToken: string) {
    if (typeof window === 'undefined') return;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
  }

  private clearTokens() {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  // ==================== Authentication ====================

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/api/v1/auth/register', data);
    this.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  }

  async login(data: LoginRequest): Promise<AuthResponse> {
    // FastAPI OAuth2PasswordRequestForm expects form data
    const params = new URLSearchParams();
    params.append('username', data.username);
    params.append('password', data.password);

    const response = await this.client.post<AuthResponse>(
      '/api/v1/auth/login',
      params.toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    this.setTokens(response.data.access_token, response.data.refresh_token);
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    return response.data;
  }

  async activateDemo(data: DemoActivateRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>(
      '/api/v1/auth/demo-activate',
      data
    );

    this.setTokens(response.data.access_token, response.data.refresh_token);
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/api/v1/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      this.clearTokens();
    }
  }

  async refreshToken(): Promise<boolean> {
    if (this.refreshing) return false;

    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    this.refreshing = true;

    try {
      const response = await this.client.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      });

      this.setTokens(response.data.access_token, response.data.refresh_token);
      this.refreshing = false;
      return true;
    } catch (error) {
      this.refreshing = false;
      return false;
    }
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/api/v1/auth/me');
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(response.data));
    }
    return response.data;
  }

  // ==================== Admin Operations ====================

  async generateDemoLink(data: {
    max_contracts: number;
    max_llm_requests: number;
    expires_in_hours: number;
    campaign?: string;
  }): Promise<DemoLinkResponse> {
    const response = await this.client.post<DemoLinkResponse>(
      '/api/v1/auth/admin/demo-link',
      data
    );
    return response.data;
  }

  async createUser(data: {
    email: string;
    name: string;
    role: string;
    subscription_tier: string;
  }): Promise<any> {
    const response = await this.client.post('/api/v1/auth/admin/users', data);
    return response.data;
  }

  async updateUserRole(
    userId: string,
    data: { role: string; subscription_tier?: string }
  ): Promise<any> {
    const response = await this.client.patch(
      `/api/v1/auth/admin/users/${userId}/role`,
      data
    );
    return response.data;
  }

  async listUsers(params?: {
    page?: number;
    limit?: number;
    role?: string;
    search?: string;
    is_demo?: boolean;
  }): Promise<any> {
    const response = await this.client.get('/api/v1/auth/admin/users', { params });
    return response.data;
  }

  async getAnalytics(): Promise<any> {
    const response = await this.client.get('/api/v1/auth/admin/analytics');
    return response.data;
  }

  // ==================== Contract Operations ====================

  async uploadContract(file: File, metadata?: any): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const response = await this.client.post('/api/v1/contracts/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 2 minutes for large files
    });

    return response.data;
  }

  async analyzeContract(contractId: string): Promise<any> {
    const response = await this.client.post(`/api/v1/contracts/${contractId}/analyze`);
    return response.data;
  }

  async getContract(contractId: string): Promise<any> {
    const response = await this.client.get(`/api/v1/contracts/${contractId}`);
    return response.data;
  }

  async listContracts(params?: {
    page?: number;
    limit?: number;
    status?: string;
  }): Promise<any> {
    const response = await this.client.get('/api/v1/contracts', { params });
    return response.data;
  }

  async exportContract(contractId: string, format: string): Promise<Blob> {
    const response = await this.client.get(
      `/api/v1/contracts/${contractId}/export`,
      {
        params: { format },
        responseType: 'blob',
      }
    );
    return response.data;
  }
}

// Export singleton instance
const api = new APIClient();
export default api;
