export const queryKeys = {
  articles: {
    all: ["articles"] as const,
    list: (status: string) => ["articles", "list", { status }] as const,
    detail: (id: string) => ["articles", "detail", id] as const,
  },
  feeds: {
    all: ["feeds"] as const,
    list: () => ["feeds", "list"] as const,
  },
}
