/**
 * API client for OnCall Copilot backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiError {
  detail: string;
}

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("token");
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("token", token);
      } else {
        localStorage.removeItem("token");
      }
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    if (this.token) {
      (headers as Record<string, string>)["Authorization"] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: "An error occurred",
      }));
      throw new Error(error.detail);
    }

    return response.json();
  }

  // Auth endpoints
  async signup(email: string, password: string, name: string) {
    const data = await this.request<{ access_token: string }>("/api/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async login(email: string, password: string) {
    const data = await this.request<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async getCurrentUser() {
    return this.request<User>("/api/v1/auth/me");
  }

  logout() {
    this.setToken(null);
  }

  // Incident endpoints
  async getIncidents(params?: { status?: string; limit?: number; offset?: number }) {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return this.request<IncidentsListResponse>(`/api/v1/incidents${query ? `?${query}` : ""}`);
  }

  async getIncident(id: number) {
    return this.request<Incident>(`/api/v1/incidents/${id}`);
  }

  async createIncident(data: CreateIncidentRequest) {
    return this.request<Incident>("/api/v1/incidents", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateIncident(id: number, data: UpdateIncidentRequest) {
    return this.request<Incident>(`/api/v1/incidents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  // Dashboard endpoints
  async getDashboard() {
    return this.request<DashboardResponse>("/api/v1/dashboard");
  }
}

// Types
export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  created_at: string;
}

export interface IncidentEvent {
  id: number;
  incident_id: number;
  event_type: string;
  content: string;
  actor_id: number;
  created_at: string;
}

export interface Incident {
  id: number;
  title: string;
  description: string;
  severity: "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4";
  status: "open" | "investigating" | "identified" | "monitoring" | "resolved";
  owner_id: number;
  created_at: string;
  resolved_at: string | null;
  owner: User;
  events: IncidentEvent[];
}

export interface IncidentListItem {
  id: number;
  title: string;
  description: string;
  severity: "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4";
  status: "open" | "investigating" | "identified" | "monitoring" | "resolved";
  owner_id: number;
  created_at: string;
  resolved_at: string | null;
  owner: User;
}

export interface IncidentsListResponse {
  items: IncidentListItem[];
  total: number;
}

export interface CreateIncidentRequest {
  title: string;
  description: string;
  severity?: "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4";
}

export interface UpdateIncidentRequest {
  title?: string;
  description?: string;
  severity?: "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4";
  status?: "open" | "investigating" | "identified" | "monitoring" | "resolved";
}

export interface DashboardStats {
  active_incidents: number;
  resolved_this_month: number;
  avg_resolution_time_hours: number | null;
  total_incidents: number;
}

export interface SeverityCount {
  severity: string;
  count: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface DashboardResponse {
  stats: DashboardStats;
  by_severity: SeverityCount[];
  by_status: StatusCount[];
}

export const api = new ApiClient(API_BASE_URL);
