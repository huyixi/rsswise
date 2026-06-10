export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  articles: {
    all: ["articles"] as const,
    list: (status: string) => ["articles", "list", { status }] as const,
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
