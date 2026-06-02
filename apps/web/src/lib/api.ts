const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ReadingRecommendation = "deep_read" | "skim" | "skip";

export type ArticleListItem = {
  id: string;
  title: string;
  source_title: string;
  published_at: string | null;
  one_sentence_summary: string | null;
  reading_recommendation: ReadingRecommendation | null;
  is_read: boolean;
};

export type ArticleDetail = {
  id: string;
  title: string;
  source_title: string;
  published_at: string | null;
  url: string;
  one_sentence_summary: string | null;
  reading_recommendation: ReadingRecommendation | null;
  reading_reason: string | null;
  content_markdown: string | null;
  extraction_status: "pending" | "processing" | "success" | "failed" | null;
  analysis_status: "pending" | "processing" | "success" | "failed" | null;
};

export type Feed = {
  id: string;
  url: string;
  title: string | null;
  site_url: string | null;
  favicon_url: string | null;
  last_fetched_at: string | null;
  created_at?: string;
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(message || `API request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  return parseResponse<T>(response);
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  return parseResponse<T>(response);
}

export async function apiDelete<T = unknown>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
  });

  return parseResponse<T>(response);
}
