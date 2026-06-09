export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || "/api"
).replace(/\/+$/, "");

export function buildApiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

export type ReadingRecommendation = "deep_read" | "skim" | "skip";

export type AiBlock =
  | {
      type: "reading_question"
      title: "带读问题"
      content: string
      order: number
    }
  | {
      type: "highlights"
      title: "Highlights"
      content: Array<{
        text: string
        quote_verified: boolean
      }>
      order: number
    }
  | {
      type: "summary"
      title: "一句话摘要"
      content: string
      order: number
    }
  | {
      type: "reading_reason"
      title: "阅读理由"
      content: string
      order: number
    }
  | {
      type: "chapters"
      title: "章节"
      content: Array<{
        title: string
      }>
      order: number
    }

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
  ai_blocks: AiBlock[] | null;
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

export type EmailDigestSettings = {
  recipient_email: string | null;
  enabled: boolean;
  send_interval_days: number;
  send_time: string;
  timezone: "Asia/Shanghai";
  last_run_date: string | null;
  last_sent_at: string | null;
  last_attempted_at: string | null;
  last_send_status: string | null;
  last_send_error: string | null;
  last_sent_article_count: number;
};

export type EmailDigestSettingsUpdate = {
  recipient_email: string | null;
  enabled: boolean;
  send_interval_days: number;
  send_time: string;
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const rawMessage = await response.text().catch(() => "");
    let message = rawMessage;
    if (rawMessage) {
      try {
        const data = JSON.parse(rawMessage) as { detail?: unknown };
        if (typeof data.detail === "string") {
          message = data.detail;
        }
      } catch {
        message = rawMessage;
      }
    }
    throw new Error(message || `API request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    credentials: "include",
  });
  return parseResponse<T>(response);
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    method: "POST",
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  return parseResponse<T>(response);
}

export async function apiPut<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    method: "PUT",
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  return parseResponse<T>(response);
}

export async function apiDelete<T = unknown>(path: string): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    method: "DELETE",
    credentials: "include",
  });

  return parseResponse<T>(response);
}

export function openApiEventSource(path: string) {
  return new EventSource(buildApiUrl(path), { withCredentials: true });
}
