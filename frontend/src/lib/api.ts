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

  // Investigation endpoints
  async investigateIncident(id: number) {
    return this.request<InvestigationResponse>(`/api/v1/incidents/${id}/investigate`, {
      method: "POST",
    });
  }

  async getInvestigations(incidentId: number) {
    return this.request<InvestigationsListResponse>(`/api/v1/incidents/${incidentId}/investigations`);
  }

  async getInvestigation(id: number) {
    return this.request<InvestigationResponse>(`/api/v1/investigations/${id}`);
  }

  async getOllamaStatus() {
    return this.request<OllamaStatus>("/api/v1/ollama/status");
  }

  // Postmortem endpoints
  async generatePostmortem(incidentId: number) {
    return this.request<PostmortemResponse>(`/api/v1/incidents/${incidentId}/postmortem`, {
      method: "POST",
    });
  }

  async getPostmortem(incidentId: number) {
    return this.request<PostmortemResponse>(`/api/v1/incidents/${incidentId}/postmortem`);
  }

  // Analytics endpoints
  async getAnalytics(days: number = 30) {
    return this.request<AnalyticsResponse>(`/api/v1/analytics?days=${days}`);
  }

  // Document endpoints
  async getDocuments(params?: { limit?: number; offset?: number }) {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return this.request<DocumentsListResponse>(`/api/v1/documents${query ? `?${query}` : ""}`);
  }

  async uploadDocument(file: File, title: string, documentType: string, incidentId?: number) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);
    formData.append("document_type", documentType);
    if (incidentId) formData.append("incident_id", String(incidentId));

    const headers: HeadersInit = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseUrl}/api/v1/documents`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(error.detail);
    }

    return response.json() as Promise<Document>;
  }

  // Search endpoint
  async search(query: string, limit: number = 10) {
    return this.request<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  }

  // Repository endpoints
  async getRepositories() {
    return this.request<RepositoriesListResponse>("/api/v1/repositories");
  }

  async connectRepository(fullName: string, accessToken: string) {
    return this.request<Repository>("/api/v1/repositories", {
      method: "POST",
      body: JSON.stringify({
        github_full_name: fullName,
        access_token: accessToken,
      }),
    });
  }

  async disconnectRepository(id: number) {
    return this.request<void>(`/api/v1/repositories/${id}`, {
      method: "DELETE",
    });
  }

  async getCorrelatedCommits(incidentId: number, windowMinutes: number = 60) {
    return this.request<CorrelatedCommitsResponse>(
      `/api/v1/incidents/${incidentId}/correlated-commits?window_minutes=${windowMinutes}`
    );
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

// Investigation types
export interface PossibleCause {
  cause: string;
  confidence: number;
  evidence_ids: string[];
}

export interface EvidenceItem {
  evidence_id: string;
  source_type: string;
  source_title: string;
  content: string;
  similarity: number | null;
  cited_in_causes: boolean;
  cited_in_actions: boolean;
}

export interface CitationValidation {
  is_valid: boolean;
  errors: string[];
}

export interface InvestigationResponse {
  id: number | null;
  incident_id: number;
  summary: string;
  severity_estimate: string;
  confidence: number;
  possible_causes: PossibleCause[];
  recommended_actions: string[];
  insufficient_evidence: boolean;
  evidence: EvidenceItem[];
  processing_time_ms: number;
  model_name: string;
  citation_validation: CitationValidation;
  created_at: string | null;
}

export interface InvestigationSummary {
  id: number;
  incident_id: number;
  summary: string;
  severity_estimate: string;
  confidence: number;
  insufficient_evidence: boolean;
  evidence_count: number;
  model_name: string;
  processing_time_ms: number;
  created_at: string;
}

export interface InvestigationsListResponse {
  items: InvestigationSummary[];
  total: number;
}

export interface OllamaStatus {
  healthy: boolean;
  model_available: boolean;
  model_name: string;
  base_url: string;
}

// Postmortem types
export interface PostmortemResponse {
  id: number;
  incident_id: number;
  content: string;
  model_name: string;
  processing_time_ms: number;
  is_new?: boolean;
  created_at?: string;
  updated_at?: string;
}

// Analytics types
export interface IncidentTrend {
  date: string;
  count: number;
  resolved: number;
}

export interface SeverityDistribution {
  severity: string;
  count: number;
  percentage: number;
}

export interface TopRootCause {
  cause: string;
  count: number;
  avg_confidence: number;
}

export interface ResolutionStats {
  avg_resolution_hours: number;
  median_resolution_hours: number;
  min_resolution_hours: number;
  max_resolution_hours: number;
}

export interface AnalyticsResponse {
  total_incidents: number;
  active_incidents: number;
  resolved_incidents: number;
  avg_resolution_hours: number;
  incidents_by_day: IncidentTrend[];
  severity_distribution: SeverityDistribution[];
  top_root_causes: TopRootCause[];
  resolution_stats: ResolutionStats | null;
}

// Document types
export interface Document {
  id: number;
  title: string;
  document_type: string;
  filename: string;
  file_size: number;
  mime_type: string;
  incident_id: number | null;
  created_at: string;
}

export interface DocumentsListResponse {
  items: Document[];
  total: number;
}

// Search types
export interface SearchResult {
  chunk_id: number;
  document_id: number;
  document_title: string;
  document_type: string;
  content: string;
  similarity: number;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
}

// Repository types
export interface Repository {
  id: number;
  github_full_name: string;
  github_url: string;
  default_branch: string;
  created_at: string;
  last_synced_at: string | null;
}

export interface RepositoriesListResponse {
  items: Repository[];
  total: number;
}

export interface Commit {
  sha: string;
  short_sha: string;
  message: string;
  author_name: string;
  committed_at: string;
  url: string;
  files_changed: string[];
}

export interface CorrelatedCommit {
  evidence_id: string;
  commit: Commit;
  minutes_before_incident: number;
  relevance_score: number;
  correlation_reason: string;
}

export interface CorrelatedCommitsResponse {
  incident_id: number;
  repository_id: number;
  window_minutes: number;
  commits: CorrelatedCommit[];
  total: number;
}

export const api = new ApiClient(API_BASE_URL);
