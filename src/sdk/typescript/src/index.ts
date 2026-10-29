export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  rank: number;
  retrieval_method: string;
  payload: Record<string, any>;
  source_uri: string;
  chunk_index: number;
}

export interface SearchRequest {
  query: string;
  app_id: string;
  collection_id: string;
  top_k?: number;
  filter_conditions?: Record<string, any>;
  use_hybrid?: boolean;
}

export interface SearchResponse {
  results: SearchResult[];
}

export interface ContextResponse {
  context: string;
  sources: SearchResult[];
}

export interface AskRequest {
  query: string;
  app_id: string;
  collection_id: string;
  top_k?: number;
  filter_conditions?: Record<string, any>;
  model?: string;
  max_tokens?: number;
  temperature?: number;
}

export interface AskResponse {
  answer: string;
  sources: Array<{
    chunk_id: string;
    document_id: string;
    source_uri: string;
    chunk_index: number;
    score: number;
  }>;
  model: string;
  retrieval_results_count: number;
  grounded: boolean;
}

export interface FeedbackRequest {
  app_id: string;
  collection_id: string;
  query: string;
  response?: string;
  retrieved_chunks: Array<Record<string, any>>;
  feedback_type: 'helpful' | 'not_helpful' | 'correct' | 'incorrect' | 'relevant' | 'irrelevant' | 'missing_info' | 'outdated' | 'wrong_source' | 'hallucination' | 'duplicate' | 'wrong_extraction';
  rating?: number;
  explanation?: string;
}

export interface FeedbackResponse {
  case_id: string;
  status: string;
}

export interface ReviewCase {
  id: string;
  application_id: string;
  collection_id: string;
  query: string;
  response?: string;
  retrieved_chunks_json: string;
  feedback_type: string;
  rating?: number;
  explanation?: string;
  status: string;
  resolution_notes?: string;
  reviewer_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ResolveReviewRequest {
  status: 'reviewed' | 'accepted' | 'rejected' | 'resolved';
  notes?: string;
  reviewer_id: string;
}

export interface AnnotationCreate {
  app_id: string;
  collection_id: string;
  question: string;
  verified_answer: string;
  review_case_id?: string;
  source_refs?: Array<Record<string, any>>;
  created_by?: string;
}

export interface AnnotationResponse {
  id: string;
  status: string;
}

export interface ApplicationCreate {
  id: string;
  name: string;
  description?: string;
  api_key?: string;
}

export interface Application {
  id: string;
  name: string;
  description?: string;
  created_at: string;
}

export interface CollectionCreate {
  id: string;
  name: string;
  description?: string;
  embedding_model?: string;
  chunk_strategy?: string;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface Collection {
  id: string;
  application_id: string;
  name: string;
  embedding_model: string;
  embedding_dim: number;
  chunk_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  created_at: string;
}

export interface IngestTextRequest {
  text: string;
  source_uri: string;
  document_id?: string;
  metadata?: Record<string, any>;
}

export interface IngestResponse {
  success: boolean;
  document_id: string;
  chunks_created: number;
  message: string;
  content_hash: string;
}

export interface ModelsResponse {
  available: string[];
  default?: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface ReadinessResponse {
  status: string;
  checks: Record<string, string>;
}

export class LocalRAGClient {
  private baseUrl: string;
  private apiKey?: string;

  constructor(baseUrl: string = "http://127.0.0.1:8000", apiKey?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string> || {}),
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetail: string = response.statusText;
      try {
        const errorJson = await response.json();
        if (errorJson && typeof errorJson === 'object' && 'detail' in errorJson) {
          errorDetail = String(errorJson.detail);
        }
      } catch {
        // Ignore parse errors
      }
      throw new Error(`HTTP ${response.status}: ${errorDetail}`);
    }

    return response.json() as Promise<T>;
  }

  // Health
  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/");
  }

  async ready(): Promise<ReadinessResponse> {
    return this.request<ReadinessResponse>("/health/ready");
  }

  // Applications
  async registerApplication(app: ApplicationCreate): Promise<Application> {
    return this.request<Application>("/applications/", {
      method: "POST",
      body: JSON.stringify(app),
    });
  }

  async getApplication(appId: string): Promise<Application> {
    return this.request<Application>(`/applications/${appId}`);
  }

  async listApplications(): Promise<Application[]> {
    return this.request<Application[]>("/applications/");
  }

  // Collections
  async createCollection(appId: string, collection: CollectionCreate): Promise<Collection> {
    return this.request<Collection>(`/applications/${appId}/collections`, {
      method: "POST",
      body: JSON.stringify(collection),
    });
  }

  async getCollection(appId: string, collectionId: string): Promise<Collection> {
    return this.request<Collection>(`/applications/${appId}/collections/${collectionId}`);
  }

  async listCollections(appId: string): Promise<Collection[]> {
    return this.request<Collection[]>(`/applications/${appId}/collections`);
  }

  // Ingestion
  async ingestText(request: IngestTextRequest): Promise<IngestResponse> {
    return this.request<IngestResponse>("/ingest/text", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async ingestFile(
    appId: string,
    collectionId: string,
    file: File,
    documentId?: string,
    metadata?: Record<string, any>
  ): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("app_id", appId);
    formData.append("collection_id", collectionId);
    if (documentId) formData.append("document_id", documentId);
    if (metadata) formData.append("metadata", JSON.stringify(metadata));

    const response = await fetch(`${this.baseUrl}/ingest/file`, {
      method: "POST",
      headers: this.apiKey ? { "Authorization": `Bearer ${this.apiKey}` } : {},
      body: formData,
    });

    if (!response.ok) {
      let errorDetail: string = response.statusText;
      try {
        const errorJson = await response.json();
        if (errorJson && typeof errorJson === 'object' && 'detail' in errorJson) {
          errorDetail = String(errorJson.detail);
        }
      } catch {
        // Ignore parse errors
      }
      throw new Error(`HTTP ${response.status}: ${errorDetail}`);
    }

    return response.json() as Promise<IngestResponse>;
  }

  async deleteDocument(appId: string, collectionId: string, documentId: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/ingest/${appId}/${collectionId}/${documentId}`, {
      method: "DELETE",
    });
  }

  // Search
  async search(request: SearchRequest): Promise<SearchResult[]> {
    const response = await this.request<SearchResponse>("/search", {
      method: "POST",
      body: JSON.stringify(request),
    });
    return response.results;
  }

  async searchVector(request: SearchRequest): Promise<SearchResult[]> {
    const response = await this.request<SearchResponse>("/search/vector", {
      method: "POST",
      body: JSON.stringify(request),
    });
    return response.results;
  }

  async searchLexical(request: Omit<SearchRequest, "use_hybrid">): Promise<SearchResult[]> {
    const response = await this.request<SearchResponse>("/search/lexical", {
      method: "POST",
      body: JSON.stringify(request),
    });
    return response.results;
  }

  async getContext(request: Omit<SearchRequest, "use_hybrid">): Promise<ContextResponse> {
    return this.request<ContextResponse>("/search/context", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // Generation
  async ask(request: AskRequest): Promise<AskResponse> {
    return this.request<AskResponse>("/generate/ask", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async listGenerationModels(): Promise<ModelsResponse> {
    return this.request<ModelsResponse>("/generate/models");
  }

  // Feedback
  async submitFeedback(request: FeedbackRequest): Promise<FeedbackResponse> {
    return this.request<FeedbackResponse>("/feedback/", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async listPendingReviews(appId: string): Promise<ReviewCase[]> {
    return this.request<ReviewCase[]>(`/feedback/${appId}/pending`);
  }

  async listAllReviews(appId: string): Promise<ReviewCase[]> {
    return this.request<ReviewCase[]>(`/feedback/${appId}/all`);
  }

  async resolveReview(appId: string, caseId: string, request: ResolveReviewRequest): Promise<{ success: boolean; message: string }> {
    return this.request(`/feedback/${appId}/cases/${caseId}/resolve`, {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async createAnnotation(request: AnnotationCreate): Promise<AnnotationResponse> {
    return this.request<AnnotationResponse>("/feedback/annotations", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async listAnnotations(appId: string, collectionId: string): Promise<Array<Record<string, any>>> {
    return this.request(`/feedback/annotations/${appId}/${collectionId}`);
  }
}

// Factory function
export function createClient(baseUrl?: string, apiKey?: string): LocalRAGClient {
  return new LocalRAGClient(baseUrl, apiKey);
}