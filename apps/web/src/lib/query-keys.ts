export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  articles: {
    all: ["articles"] as const,
    list: (status: string, feedId?: string | null) =>
      ["articles", "list", { status, feedId: feedId || undefined }] as const,
    detail: (id: string) => ["articles", "detail", id] as const,
  },
  feeds: {
    all: ["feeds"] as const,
    list: () => ["feeds", "list"] as const,
  },
  feedImports: {
    all: ["feedImports"] as const,
    detail: (id: string) => ["feedImports", id] as const,
  },
  settings: {
    all: ["settings"] as const,
    emailDigest: () => ["settings", "email-digest"] as const,
  },
};
