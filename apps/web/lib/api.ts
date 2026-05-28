const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API GET ${path} failed`);
  }
  return response.json() as Promise<T>;
}

export async function apiPost(path: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}${path}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`API POST ${path} failed`);
  }
}
